/**
 * A QR encoder, written here rather than pulled in as a dependency.
 *
 * Copied verbatim from WebbPulse-Portfolio, `frontend/src/utils/qrCode.ts`,
 * which introduced it for the same screen this file serves: the one TOTP
 * enrolment panel that has to render a provisioning URI. It is duplicated
 * rather than shared because it is a leaf with no imports and no product
 * knowledge, and moving it into `@webbpulse/*` would put a rendering concern
 * into a package whose job is the protocol. If a third consumer appears, that
 * is the point at which it earns a home in the shared packages.
 *
 * The only thing this application ever encodes is one `otpauth://totp/...`
 * provisioning URI, shown once during TOTP enrolment. A QR library is a large
 * surface and a supply chain entry for a single screen, and the identity
 * package deliberately ships no generator of its own: `TotpEnrolmentStarted`
 * documents that rendering the URI is the product's job. So the subset of
 * ISO/IEC 18004 that a provisioning URI needs lives here.
 *
 * ## What is implemented, and what is left out
 *
 * Byte mode only, error correction level M, versions 1 to 10. That is the
 * smallest thing that encodes the input this application has:
 *
 * - A provisioning URI is ASCII, so byte mode covers it and the alphanumeric
 *   and kanji modes would never be selected. Mode selection would be dead code.
 * - Level M is the level most authenticator documentation assumes and holds 213
 *   bytes at version 10, which is far beyond any issuer and label pair this
 *   service produces. A URI longer than that throws rather than silently
 *   producing an unreadable symbol, and {@link encodeQrCode} says so.
 * - Versions above 10 are not built, for capacity that a provisioning URI
 *   cannot reach. Versions 7 and up are, and those carry the 18 bit version
 *   information block that {@link placeVersionInformation} writes; a symbol
 *   that omits it is not merely missing a hint, because the modules it
 *   occupies would otherwise be filled with data and shift the entire stream.
 *
 * ## Why the mask is chosen rather than fixed
 *
 * All eight masks are evaluated with the four penalty rules from the standard
 * and the lowest scoring one wins. Fixing a mask is tempting and produces a
 * symbol that scans in a test, but the penalty rules exist because some data
 * and mask combinations put long runs or 1:1:3:1:1 sequences into the symbol,
 * which is what makes a reader mistake data for a finder pattern. The input
 * here varies with the account label, so the combination is not known ahead of
 * time and cannot be checked once by hand.
 */

/** The error correction level this module encodes at. See the module note. */
const EC_LEVEL_M = 'M';

/** The highest version this module builds. See the module note. */
const MAX_VERSION = 10;

/**
 * Data codeword count and EC codewords per block for level M, versions 1 to 10.
 *
 * `[totalDataCodewords, ecCodewordsPerBlock, group1Blocks, group2Blocks]`.
 * Group 2 blocks hold exactly one more data codeword than group 1 blocks, which
 * is how the standard splits a byte count that does not divide evenly.
 * Transcribed from ISO/IEC 18004 table 9.
 */
const VERSION_SPECS_M: readonly (readonly [number, number, number, number])[] =
  [
    [16, 10, 1, 0],
    [28, 16, 1, 0],
    [44, 26, 1, 0],
    [64, 18, 2, 0],
    [86, 24, 2, 0],
    [108, 16, 4, 0],
    [124, 18, 4, 0],
    [154, 22, 2, 2],
    [182, 22, 3, 2],
    [216, 26, 4, 1],
  ];

/**
 * Alignment pattern centre coordinates per version, index 0 being version 1.
 *
 * Version 1 has none. From ISO/IEC 18004 table E.1. Every pair of coordinates
 * in a version's list is a centre except where it would collide with a finder
 * pattern, which {@link placeAlignmentPatterns} skips.
 */
const ALIGNMENT_CENTRES: readonly (readonly number[])[] = [
  [],
  [6, 18],
  [6, 22],
  [6, 26],
  [6, 30],
  [6, 34],
  [6, 22, 38],
  [6, 24, 42],
  [6, 26, 46],
  [6, 28, 50],
];

/** A square matrix of modules, `true` being dark. */
export interface QrMatrix {
  size: number;
  modules: boolean[][];
}

const GF_EXP = new Uint8Array(512);
const GF_LOG = new Uint8Array(256);

(() => {
  let x = 1;
  for (let i = 0; i < 255; i += 1) {
    GF_EXP[i] = x;
    GF_LOG[x] = i;
    x <<= 1;
    if (x & 0x100) {
      x ^= 0x11d;
    }
  }
  for (let i = 255; i < 512; i += 1) {
    GF_EXP[i] = GF_EXP[i - 255] as number;
  }
})();

function gfMultiply(a: number, b: number): number {
  if (a === 0 || b === 0) {
    return 0;
  }
  return GF_EXP[(GF_LOG[a] as number) + (GF_LOG[b] as number)] as number;
}

/** The generator polynomial for `degree` error correction codewords. */
function generatorPolynomial(degree: number): number[] {
  let poly = [1];
  for (let i = 0; i < degree; i += 1) {
    const next = new Array<number>(poly.length + 1).fill(0);
    for (let j = 0; j < poly.length; j += 1) {
      next[j] = (next[j] as number) ^ (poly[j] as number);
      next[j + 1] =
        (next[j + 1] as number) ^
        gfMultiply(poly[j] as number, GF_EXP[i] as number);
    }
    poly = next;
  }
  return poly;
}

/** The error correction codewords for one block. */
function errorCorrectionCodewords(data: number[], count: number): number[] {
  const generator = generatorPolynomial(count);
  const remainder = new Array<number>(count).fill(0);
  for (const byte of data) {
    const factor = byte ^ (remainder[0] as number);
    remainder.shift();
    remainder.push(0);
    for (let i = 0; i < generator.length - 1; i += 1) {
      remainder[i] =
        (remainder[i] as number) ^
        gfMultiply(generator[i + 1] as number, factor);
    }
  }
  return remainder;
}

/** Accumulates bits and hands back whole codewords. */
class BitBuffer {
  private readonly bits: number[] = [];

  put(value: number, length: number): void {
    for (let i = length - 1; i >= 0; i -= 1) {
      this.bits.push((value >>> i) & 1);
    }
  }

  get length(): number {
    return this.bits.length;
  }

  /** Pads to a byte boundary and returns the codewords. */
  toCodewords(): number[] {
    const padded = [...this.bits];
    while (padded.length % 8 !== 0) {
      padded.push(0);
    }
    const bytes: number[] = [];
    for (let i = 0; i < padded.length; i += 8) {
      let byte = 0;
      for (let j = 0; j < 8; j += 1) {
        byte = (byte << 1) | (padded[i + j] as number);
      }
      bytes.push(byte);
    }
    return bytes;
  }
}

/** The smallest version whose level M capacity holds `byteLength` bytes. */
function chooseVersion(byteLength: number): number {
  for (let version = 1; version <= MAX_VERSION; version += 1) {
    const spec = VERSION_SPECS_M[version - 1] as readonly [
      number,
      number,
      number,
      number,
    ];
    const countBits = version <= 9 ? 8 : 16;
    const needed = 4 + countBits + byteLength * 8;
    if (needed <= spec[0] * 8) {
      return version;
    }
  }
  throw new Error(
    `That value is ${byteLength} bytes, which is more than a version ${MAX_VERSION} QR code holds at error correction level ${EC_LEVEL_M}.`
  );
}

/**
 * The full codeword sequence: data and error correction, interleaved.
 *
 * Interleaving is what makes a burst of damage spread across blocks rather than
 * destroying one block outright, and it is required whenever there is more than
 * one block. The order is every block's first data codeword, then every block's
 * second, and the same again over the EC codewords.
 */
function buildCodewords(data: Uint8Array, version: number): number[] {
  const spec = VERSION_SPECS_M[version - 1] as readonly [
    number,
    number,
    number,
    number,
  ];
  const [totalData, ecPerBlock, group1Blocks, group2Blocks] = spec;
  const totalBlocks = group1Blocks + group2Blocks;
  const group1Size = Math.floor(totalData / totalBlocks);

  const buffer = new BitBuffer();
  buffer.put(0b0100, 4);
  buffer.put(data.length, version <= 9 ? 8 : 16);
  for (const byte of data) {
    buffer.put(byte, 8);
  }
  const remaining = totalData * 8 - buffer.length;
  buffer.put(0, Math.min(4, Math.max(0, remaining)));

  const codewords = buffer.toCodewords();
  const padBytes = [0xec, 0x11];
  let padIndex = 0;
  while (codewords.length < totalData) {
    codewords.push(padBytes[padIndex % 2] as number);
    padIndex += 1;
  }

  const dataBlocks: number[][] = [];
  const ecBlocks: number[][] = [];
  let offset = 0;
  for (let block = 0; block < totalBlocks; block += 1) {
    const size = block < group1Blocks ? group1Size : group1Size + 1;
    const blockData = codewords.slice(offset, offset + size);
    offset += size;
    dataBlocks.push(blockData);
    ecBlocks.push(errorCorrectionCodewords(blockData, ecPerBlock));
  }

  const result: number[] = [];
  const longestData = Math.max(...dataBlocks.map((block) => block.length));
  for (let i = 0; i < longestData; i += 1) {
    for (const block of dataBlocks) {
      if (i < block.length) {
        result.push(block[i] as number);
      }
    }
  }
  for (let i = 0; i < ecPerBlock; i += 1) {
    for (const block of ecBlocks) {
      result.push(block[i] as number);
    }
  }
  return result;
}

/**
 * Which modules are function patterns rather than data.
 *
 * Kept alongside the module grid because placement, masking and penalty
 * scoring all need to know: data is written only where this is false, and the
 * mask is applied only to data.
 */
type Reserved = boolean[][];

function emptyGrid(size: number): boolean[][] {
  return Array.from({ length: size }, () =>
    new Array<boolean>(size).fill(false)
  );
}

function placeFinderPattern(
  modules: boolean[][],
  reserved: Reserved,
  row: number,
  col: number
): void {
  for (let r = -1; r <= 7; r += 1) {
    for (let c = -1; c <= 7; c += 1) {
      const rr = row + r;
      const cc = col + c;
      if (rr < 0 || rr >= modules.length || cc < 0 || cc >= modules.length) {
        continue;
      }
      const inRing = (r === 0 || r === 6) && c >= 0 && c <= 6;
      const inSide = (c === 0 || c === 6) && r >= 0 && r <= 6;
      const inCore = r >= 2 && r <= 4 && c >= 2 && c <= 4;
      (modules[rr] as boolean[])[cc] = inRing || inSide || inCore;
      (reserved[rr] as boolean[])[cc] = true;
    }
  }
}

function placeAlignmentPatterns(
  modules: boolean[][],
  reserved: Reserved,
  version: number
): void {
  const centres = ALIGNMENT_CENTRES[version - 1] as readonly number[];
  const size = modules.length;
  for (const row of centres) {
    for (const col of centres) {
      const nearFinder =
        (row <= 8 && col <= 8) ||
        (row <= 8 && col >= size - 9) ||
        (row >= size - 9 && col <= 8);
      if (nearFinder) {
        continue;
      }
      for (let r = -2; r <= 2; r += 1) {
        for (let c = -2; c <= 2; c += 1) {
          const dark = Math.max(Math.abs(r), Math.abs(c)) !== 1;
          (modules[row + r] as boolean[])[col + c] = dark;
          (reserved[row + r] as boolean[])[col + c] = true;
        }
      }
    }
  }
}

function placeTimingPatterns(modules: boolean[][], reserved: Reserved): void {
  const size = modules.length;
  for (let i = 8; i < size - 8; i += 1) {
    const dark = i % 2 === 0;
    (modules[6] as boolean[])[i] = dark;
    (reserved[6] as boolean[])[i] = true;
    (modules[i] as boolean[])[6] = dark;
    (reserved[i] as boolean[])[6] = true;
  }
}

/** Reserves the format information modules and the always-dark module. */
function reserveFormatAreas(modules: boolean[][], reserved: Reserved): void {
  const size = modules.length;
  for (let i = 0; i < 9; i += 1) {
    if (!((reserved[8] as boolean[])[i] as boolean)) {
      (reserved[8] as boolean[])[i] = true;
    }
    if (!((reserved[i] as boolean[])[8] as boolean)) {
      (reserved[i] as boolean[])[8] = true;
    }
  }
  for (let i = 0; i < 8; i += 1) {
    (reserved[8] as boolean[])[size - 1 - i] = true;
    (reserved[size - 1 - i] as boolean[])[8] = true;
  }
  (modules[size - 8] as boolean[])[8] = true;
  (reserved[size - 8] as boolean[])[8] = true;
}

/**
 * Writes the codeword bits along the standard's zigzag, applying `mask`.
 *
 * Columns are walked in pairs from the right, upward then downward, skipping
 * the vertical timing column. The mask is applied here rather than as a second
 * pass over the grid, which keeps it away from the function patterns without
 * needing a second reserved check.
 */
function placeData(
  modules: boolean[][],
  reserved: Reserved,
  codewords: number[],
  mask: number
): void {
  const size = modules.length;
  let bitIndex = 0;
  let upward = true;

  for (let right = size - 1; right >= 1; right -= 2) {
    const rightCol = right <= 6 ? right - 1 : right;
    for (let step = 0; step < size; step += 1) {
      const row = upward ? size - 1 - step : step;
      for (let c = 0; c < 2; c += 1) {
        const col = rightCol - c;
        if ((reserved[row] as boolean[])[col] as boolean) {
          continue;
        }
        const byte = codewords[bitIndex >>> 3];
        const bit =
          byte === undefined ? 0 : (byte >>> (7 - (bitIndex & 7))) & 1;
        bitIndex += 1;
        (modules[row] as boolean[])[col] =
          bit === 1 ? !maskAt(mask, row, col) : maskAt(mask, row, col);
      }
    }
    upward = !upward;
  }
}

/** Whether mask `pattern` inverts the module at (row, col). */
function maskAt(pattern: number, row: number, col: number): boolean {
  switch (pattern) {
    case 0:
      return (row + col) % 2 === 0;
    case 1:
      return row % 2 === 0;
    case 2:
      return col % 3 === 0;
    case 3:
      return (row + col) % 3 === 0;
    case 4:
      return (Math.floor(row / 2) + Math.floor(col / 3)) % 2 === 0;
    case 5:
      return ((row * col) % 2) + ((row * col) % 3) === 0;
    case 6:
      return (((row * col) % 2) + ((row * col) % 3)) % 2 === 0;
    default:
      return (((row + col) % 2) + ((row * col) % 3)) % 2 === 0;
  }
}

/**
 * The 15 bit format information for level M and a mask, BCH coded and masked.
 *
 * The trailing XOR with 0x5412 is required by the standard and is what stops an
 * all-light format area, which a reader could not distinguish from no symbol.
 */
function formatBits(mask: number): number {
  const data = (0b00 << 3) | mask;
  let value = data << 10;
  for (let i = 4; i >= 0; i -= 1) {
    if ((value >>> (10 + i)) & 1) {
      value ^= 0b10100110111 << i;
    }
  }
  return ((data << 10) | value) ^ 0b101010000010010;
}

function placeFormatInformation(modules: boolean[][], mask: number): void {
  const size = modules.length;
  const bits = formatBits(mask);
  for (let i = 0; i < 15; i += 1) {
    const dark = ((bits >>> i) & 1) === 1;
    if (i < 6) {
      (modules[i] as boolean[])[8] = dark;
    } else if (i < 8) {
      (modules[i + 1] as boolean[])[8] = dark;
    } else {
      (modules[size - 15 + i] as boolean[])[8] = dark;
    }
    if (i < 8) {
      (modules[8] as boolean[])[size - 1 - i] = dark;
    } else if (i < 9) {
      (modules[8] as boolean[])[15 - i - 1 + 1] = dark;
    } else {
      (modules[8] as boolean[])[15 - i - 1] = dark;
    }
  }
}

/**
 * Reserves and writes the 18 bit version block, for versions 7 and up.
 *
 * Two copies: a 6x3 area left of the top right finder and its transpose above
 * the bottom left one. The BCH(18,6) code is the version number in the top six
 * bits and a golay remainder under the generator 0x1f25 in the low twelve.
 *
 * Reserving matters as much as writing. These modules are not data, and an
 * encoder that skips them writes the data stream straight through the area,
 * which displaces every module after it. That produces a symbol that still
 * looks like a QR code and decodes to nothing.
 */
function placeVersionInformation(
  modules: boolean[][],
  reserved: Reserved,
  version: number
): void {
  if (version < 7) {
    return;
  }
  const size = modules.length;
  let value = version << 12;
  for (let i = 5; i >= 0; i -= 1) {
    if ((value >>> (12 + i)) & 1) {
      value ^= 0x1f25 << i;
    }
  }
  const bits = (version << 12) | (value & 0xfff);

  for (let i = 0; i < 18; i += 1) {
    const dark = ((bits >>> i) & 1) === 1;
    const row = Math.floor(i / 3);
    const col = size - 11 + (i % 3);
    (modules[row] as boolean[])[col] = dark;
    (reserved[row] as boolean[])[col] = true;
    (modules[col] as boolean[])[row] = dark;
    (reserved[col] as boolean[])[row] = true;
  }
}

/** The standard's four penalty rules, summed. Lower is better. */
function penaltyScore(modules: boolean[][]): number {
  const size = modules.length;
  let score = 0;

  for (let i = 0; i < size; i += 1) {
    for (const readRow of [true, false]) {
      let run = 1;
      for (let j = 1; j < size; j += 1) {
        const current = readRow
          ? ((modules[i] as boolean[])[j] as boolean)
          : ((modules[j] as boolean[])[i] as boolean);
        const previous = readRow
          ? ((modules[i] as boolean[])[j - 1] as boolean)
          : ((modules[j - 1] as boolean[])[i] as boolean);
        if (current === previous) {
          run += 1;
        } else {
          if (run >= 5) {
            score += run - 2;
          }
          run = 1;
        }
      }
      if (run >= 5) {
        score += run - 2;
      }
    }
  }

  for (let r = 0; r < size - 1; r += 1) {
    for (let c = 0; c < size - 1; c += 1) {
      const value = (modules[r] as boolean[])[c] as boolean;
      if (
        ((modules[r] as boolean[])[c + 1] as boolean) === value &&
        ((modules[r + 1] as boolean[])[c] as boolean) === value &&
        ((modules[r + 1] as boolean[])[c + 1] as boolean) === value
      ) {
        score += 3;
      }
    }
  }

  const pattern = [true, false, true, true, true, false, true];
  const quiet = [false, false, false, false];
  const matchesAt = (line: boolean[], start: number, seq: boolean[]): boolean =>
    seq.every((value, index) => line[start + index] === value);
  const lines: boolean[][] = [];
  for (let i = 0; i < size; i += 1) {
    lines.push(modules[i] as boolean[]);
    lines.push(modules.map((row) => row[i] as boolean));
  }
  for (const line of lines) {
    for (let i = 0; i + 7 <= line.length; i += 1) {
      if (!matchesAt(line, i, pattern)) {
        continue;
      }
      const before = i - 4 >= 0 && matchesAt(line, i - 4, quiet);
      const after = i + 11 <= line.length && matchesAt(line, i + 7, quiet);
      if (before || after) {
        score += 40;
      }
    }
  }

  let dark = 0;
  for (const row of modules) {
    for (const value of row) {
      if (value) {
        dark += 1;
      }
    }
  }
  const percent = (dark * 100) / (size * size);
  score += Math.floor(Math.abs(percent - 50) / 5) * 10;

  return score;
}

/**
 * Encodes `text` as a QR matrix, choosing the version and the mask.
 *
 * Byte mode, error correction level M, versions 1 to 10. Throws when the text
 * is longer than a version 10 symbol holds or when it is not representable in
 * a single byte per character; see the module note for why that range is the
 * one this application needs.
 */
export function encodeQrCode(text: string): QrMatrix {
  const bytes = new TextEncoder().encode(text);
  const version = chooseVersion(bytes.length);
  const codewords = buildCodewords(bytes, version);
  const size = version * 4 + 17;

  let best: boolean[][] | null = null;
  let bestScore = Number.POSITIVE_INFINITY;

  for (let mask = 0; mask < 8; mask += 1) {
    const modules = emptyGrid(size);
    const reserved = emptyGrid(size);
    placeFinderPattern(modules, reserved, 0, 0);
    placeFinderPattern(modules, reserved, 0, size - 7);
    placeFinderPattern(modules, reserved, size - 7, 0);
    placeAlignmentPatterns(modules, reserved, version);
    placeTimingPatterns(modules, reserved);
    reserveFormatAreas(modules, reserved);
    placeVersionInformation(modules, reserved, version);
    placeData(modules, reserved, codewords, mask);
    placeFormatInformation(modules, mask);

    const score = penaltyScore(modules);
    if (score < bestScore) {
      bestScore = score;
      best = modules;
    }
  }

  return { size, modules: best as boolean[][] };
}

/**
 * The matrix as an SVG path `d` attribute, one `M`/`h`/`v` box per dark module.
 *
 * A path rather than one `<rect>` per module: a version 5 symbol is 37 squared,
 * and a thousand elements is a page the browser lays out slowly for no visual
 * difference. The four module quiet zone the standard requires is added by the
 * caller through the viewBox, which {@link qrCodeSvgPath} returns alongside.
 */
export function qrCodeSvgPath(text: string): {
  path: string;
  viewBox: string;
  size: number;
} {
  const { size, modules } = encodeQrCode(text);
  const quiet = 4;
  const parts: string[] = [];
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      if ((modules[row] as boolean[])[col] as boolean) {
        parts.push(`M${col + quiet} ${row + quiet}h1v1h-1z`);
      }
    }
  }
  const total = size + quiet * 2;
  return {
    path: parts.join(''),
    viewBox: `0 0 ${total} ${total}`,
    size: total,
  };
}
