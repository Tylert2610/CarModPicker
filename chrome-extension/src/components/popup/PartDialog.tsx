import type { FormEvent } from "react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import type {
  ApiResponse,
  PartManufacturer,
  Car,
  Category,
  PartCreate,
  PartRead,
  Retailer,
  ScrapedProductData,
} from "../../types";
import SearchableSelect from "../common/SearchableSelect";
import RecordPriceDialog from "./RecordPriceDialog";

type PartDialogView = "checking" | "record_price" | "create";

interface BlockingPart {
  id: string;
  name: string;
  source: string;
  reason: "non_ugc_exists" | "own_ugc_exists";
}

/** The frontend origin matching the configured API environment. */
async function getFrontendUrl(): Promise<string> {
  return new Promise((resolve) => {
    chrome.storage.sync.get(["apiUrl"], (settings) => {
      const apiUrl =
        (settings["apiUrl"] as string) || "https://api.carmodpicker.com/api";
      if (apiUrl.includes("localhost") || apiUrl.includes("127.0.0.1")) {
        resolve("http://localhost:4000");
      } else if (apiUrl.includes("staging")) {
        resolve("https://staging.carmodpicker.com");
      } else {
        resolve("https://www.carmodpicker.com");
      }
    });
  });
}

/** Notice offering to open the part that blocked this create. */
const BlockingPartPanel: React.FC<{
  blocking: BlockingPart;
  onDismiss: () => void;
}> = ({ blocking, onDismiss }) => {
  const [isOpening, setIsOpening] = useState(false);
  const headline =
    blocking.reason === "non_ugc_exists"
      ? "This part is already in our catalog"
      : "You already created this part";
  const subline =
    blocking.reason === "non_ugc_exists"
      ? "Community submissions can't duplicate catalog parts. Open the existing part to record a price or add missing data."
      : "You've already submitted a community-contributed part for this product. Open yours instead of making another.";
  return (
    <div className="p-4 rounded-xl bg-amber-500/15 border border-amber-500/40 text-sm text-neutral-100 space-y-2">
      <div className="font-semibold text-amber-200">{headline}</div>
      <div className="text-neutral-300">{subline}</div>
      <div className="text-xs text-neutral-400">
        <span className="font-medium">{blocking.name}</span>
        <span className="ml-2 uppercase tracking-wide">
          ({blocking.source})
        </span>
      </div>
      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={async () => {
            setIsOpening(true);
            const frontend = await getFrontendUrl();
            chrome.tabs.create({ url: `${frontend}/parts/${blocking.id}` });
            setIsOpening(false);
          }}
          className="px-3 py-1.5 rounded-lg bg-amber-500/30 hover:bg-amber-500/50 border border-amber-500/60 text-amber-100 text-xs font-semibold transition-colors"
          disabled={isOpening}
        >
          {isOpening ? "Opening…" : "Open existing part"}
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 border border-white/20 text-neutral-200 text-xs transition-colors"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
};

interface PartDialogProps {
  scrapedData: ScrapedProductData;
  onClose: () => void;
  onPartCreated: () => void;
  sendMessage: (message: {
    action: string;
    partData?: PartCreate;
    imageUrl?: string;
    limit?: number;
    searchTerm?: string;
    part_manufacturerName?: string;
    productUrl?: string;
    partId?: string;
    part_manufacturerId?: string;
    partNumber?: string;
    domain?: string;
    listingData?: {
      part_id: string;
      retailer_id: string;
      product_url?: string;
      price_cents?: number;
    };
  }) => Promise<unknown>;
}

/** The hostname of a URL, for matching a retailer, or null when unparseable. */
function domainFromUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.hostname?.toLowerCase() || null;
  } catch {
    return null;
  }
}

/** Strip a leading `www.` so domains compare equal. */
function normalizeDomain(domain: string): string {
  return domain.replace(/^www\./, "");
}

/** Strip label prefixes such as "SKU:" so part numbers dedupe correctly. */
function normalizePartNumber(raw: string): string {
  let s = raw.trim();
  const prefixes = [
    /^SKU\s*:\s*/i,
    /^Part\s*#\s*:\s*/i,
    /^Part\s*Number\s*:\s*/i,
    /^Item\s*#\s*:\s*/i,
    /^Product\s*Code\s*:\s*/i,
    /^Model\s*#?\s*:\s*/i,
    /^Code\s*:\s*/i,
  ];
  for (const re of prefixes) {
    s = s.replace(re, "");
  }
  return s.trim();
}

/** Review a scraped product, then create the part or record its price. */
const PartDialog: React.FC<PartDialogProps> = ({
  scrapedData,
  onClose,
  onPartCreated,
  sendMessage,
}) => {
  const [viewMode, setViewMode] = useState<PartDialogView>("checking");
  const [existingPart, setExistingPart] = useState<PartRead | null>(null);
  const [blockingPart, setBlockingPart] = useState<BlockingPart | null>(null);
  const [recordPriceRetailer, setRecordPriceRetailer] =
    useState<Retailer | null>(null);

  const [formData, setFormData] = useState({
    name: scrapedData.name || "",
    part_manufacturerId: null as string | null,
    partNumber: scrapedData.part_number || "",
    description: scrapedData.description || "",
    price: scrapedData.price ? (scrapedData.price / 100).toFixed(2) : "",
    url: scrapedData.product_url || "",
    imageUrl: "",
    imageUrls: scrapedData.image_urls || [],
    categoryId: null as string | null,
    carId: null as string | null,
  });

  const [pendingPartManufacturerName, setPendingPartManufacturerName] = useState<string | null>(null);
  const hasInitializedPartManufacturer = useRef(false);
  const hasInitializedCategory = useRef(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [cars, setCars] = useState<Car[]>([]);
  const [part_manufacturers, setPartManufacturers] = useState<PartManufacturer[]>([]);
  const [retailers, setRetailers] = useState<Retailer[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [imagePreview, setImagePreview] = useState(
    scrapedData.image_urls?.[0] ?? "",
  );

  const [resolvedRetailer, setResolvedRetailer] = useState<Retailer | null>(
    null,
  );
  const matchedRetailerFromList = useMemo(() => {
    const domain = domainFromUrl(formData.url || scrapedData.product_url || "");
    if (!domain || retailers.length === 0) return null;
    const normalized = normalizeDomain(domain);
    return (
      retailers.find(
        (r) => r.domain && normalizeDomain(r.domain) === normalized,
      ) ??
      retailers.find(
        (r) =>
          r.domain?.includes(normalized) || normalized.includes(r.domain || ""),
      ) ??
      null
    );
  }, [formData.url, scrapedData.product_url, retailers]);

  const matchedRetailer = resolvedRetailer ?? matchedRetailerFromList;

  useEffect(() => {
    const productUrl = scrapedData.product_url?.trim();
    if (!productUrl) {
      setViewMode("create");
      return;
    }

    const checkExisting = async () => {
      const response = (await sendMessage({
        action: "checkProductUrl",
        productUrl,
      })) as ApiResponse<{ existing_part_id: string | null }>;

      if (!response.success || !response.data) {
        setViewMode("create");
        return;
      }

      const partId = response.data.existing_part_id;
      if (partId == null) {
        setViewMode("create");
        return;
      }

      const partResponse = (await sendMessage({
        action: "getPart",
        partId,
      })) as ApiResponse<PartRead>;

      if (!partResponse.success || !partResponse.data) {
        setViewMode("create");
        return;
      }

      setExistingPart(partResponse.data);

      const domain = domainFromUrl(productUrl);
      if (domain) {
        const retailerResponse = (await sendMessage({
          action: "getOrCreateRetailerByDomain",
          domain: normalizeDomain(domain),
        })) as ApiResponse<Retailer>;
        if (retailerResponse.success && retailerResponse.data) {
          setRecordPriceRetailer(retailerResponse.data);
        }
      }

      setViewMode("record_price");
    };

    void checkExisting();
  }, [scrapedData.product_url]);

  useEffect(() => {
    if (viewMode !== "create") return;
    loadCategories();
    loadCars();
    loadPartManufacturers();
    loadRetailers();
  }, [viewMode]);

  useEffect(() => {
    if (
      hasInitializedPartManufacturer.current ||
      part_manufacturers.length === 0 ||
      !scrapedData.part_manufacturer?.trim()
    )
      return;
    hasInitializedPartManufacturer.current = true;
    const match = part_manufacturers.find(
      (b) => b.name.toLowerCase() === scrapedData.part_manufacturer!.toLowerCase(),
    );
    if (match) {
      setFormData((prev) => ({ ...prev, part_manufacturerId: match.id }));
    } else {
      setPendingPartManufacturerName(scrapedData.part_manufacturer.trim());
    }
  }, [part_manufacturers, scrapedData.part_manufacturer]);

  useEffect(() => {
    if (
      hasInitializedCategory.current ||
      categories.length === 0 ||
      !scrapedData.inferred_category
    )
      return;
    hasInitializedCategory.current = true;
    const match = categories.find(
      (c) => c.name.toLowerCase() === scrapedData.inferred_category!.toLowerCase(),
    );
    if (match) {
      setFormData((prev) => ({ ...prev, categoryId: match.id }));
    }
  }, [categories, scrapedData.inferred_category]);

  useEffect(() => {
    if (formData.imageUrl) {
      setImagePreview(formData.imageUrl);
    } else if (formData.imageUrls.length > 0 && formData.imageUrls[0]) {
      setImagePreview(formData.imageUrls[0]);
    }
  }, [formData.imageUrl, formData.imageUrls]);

  /** Load the active categories, leaving the list empty on failure. */
  const loadCategories = async () => {
    try {
      const response = (await sendMessage({
        action: "getCategories",
      })) as ApiResponse<Category[]>;

      if (response.success && Array.isArray(response.data)) {
        setCategories(response.data.filter((cat) => cat.is_active));
      }
    } catch {}
  };

  /** Load the part manufacturers, leaving the list empty on failure. */
  const loadPartManufacturers = async () => {
    try {
      const response = (await sendMessage({
        action: "getPartManufacturers",
      })) as ApiResponse<PartManufacturer[]>;
      if (response.success && Array.isArray(response.data)) {
        setPartManufacturers(response.data);
      }
    } catch {}
  };

  /** Load the retailers, leaving the list empty on failure. */
  const loadRetailers = async () => {
    try {
      const response = (await sendMessage({
        action: "getRetailers",
      })) as ApiResponse<Retailer[]>;
      if (response.success && Array.isArray(response.data)) {
        setRetailers(response.data);
      }
    } catch {}
  };

  /** Load the car generations, leaving the list empty on failure. */
  const loadCars = async () => {
    try {
      const response = (await sendMessage({
        action: "getCars",
        limit: 1000,
      })) as ApiResponse<Car[]>;

      if (response.success && Array.isArray(response.data)) {
        setCars(response.data);
      }
    } catch {}
  };

  /**
   * Resolve the retailer for the product URL, creating it when the catalog has
   * none, so a first scrape still records a listing and its price.
   */
  const ensureRetailerForCreate = async (): Promise<Retailer | null> => {
    const url = formData.url?.trim() || scrapedData.product_url;
    if (!url) return null;

    const domain = domainFromUrl(url);
    if (!domain) return null;

    const response = (await sendMessage({
      action: "getOrCreateRetailerByDomain",
      domain: normalizeDomain(domain),
    })) as ApiResponse<Retailer>;

    if (response.success && response.data) {
      setResolvedRetailer(response.data);
      return response.data;
    }
    return null;
  };

  /** Search manufacturers by name, falling back to the loaded list. */
  const searchPartManufacturers = async (searchTerm: string): Promise<PartManufacturer[]> => {
    if (!searchTerm || searchTerm.length <= 1) return part_manufacturers;
    try {
      const response = (await sendMessage({
        action: "searchPartManufacturers",
        searchTerm,
      })) as ApiResponse<PartManufacturer[]>;
      if (response.success && Array.isArray(response.data)) {
        return response.data;
      }
    } catch {}
    return part_manufacturers;
  };

  /** Search car generations by name, or return the loaded list for short terms. */
  const searchCars = async (searchTerm: string): Promise<Car[]> => {
    if (!searchTerm || searchTerm.length <= 2) {
      return cars;
    }

    try {
      const response = (await sendMessage({
        action: "searchCars",
        searchTerm,
      })) as ApiResponse<Car[]>;

      if (response.success && Array.isArray(response.data)) {
        return response.data;
      }
    } catch {}

    return [];
  };

  /** Create the part, then record its listing and open the new part page. */
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const retailer = await ensureRetailerForCreate();

      if (!formData.name.trim()) {
        setError("Part name is required");
        setIsLoading(false);
        return;
      }

      if (!formData.categoryId) {
        setError("Category is required");
        setIsLoading(false);
        return;
      }

      if (!formData.part_manufacturerId && !pendingPartManufacturerName) {
        setError("PartManufacturer is required");
        setIsLoading(false);
        return;
      }

      let part_manufacturerId: string | null = formData.part_manufacturerId;
      if (!part_manufacturerId && pendingPartManufacturerName) {
        const part_manufacturerResult = (await sendMessage({
          action: "createPartManufacturer",
          part_manufacturerName: pendingPartManufacturerName,
        })) as ApiResponse<PartManufacturer>;
        if (part_manufacturerResult.success && part_manufacturerResult.data) {
          part_manufacturerId = part_manufacturerResult.data.id;
          setPartManufacturers((prev) => [...prev, part_manufacturerResult.data!]);
        } else {
          setError(part_manufacturerResult.error || "Failed to create part_manufacturer");
          setIsLoading(false);
          return;
        }
      }

      const priceCents = formData.price
        ? Math.round(parseFloat(formData.price) * 100)
        : scrapedData.price;

      const partData: PartCreate = {
        name: formData.name.trim(),
        description: formData.description.trim() || null,
        price: priceCents,
        product_url: formData.url.trim() || null,
        category_id: formData.categoryId!,
        is_universal: false,
        car_ids: formData.carId ? [formData.carId] : [],
        part_manufacturer_id: part_manufacturerId!,
        part_number: normalizePartNumber(formData.partNumber) || null,
        image_urls: null,
        retailer_id: retailer?.id ?? null,
        price_cents: retailer && priceCents != null ? priceCents : null,
      };

      const MAX_IMAGES_PER_GLOBAL_PART = 12;
      const scrapedImageUrls = [
        ...new Set(
          [formData.imageUrl.trim() || null, ...formData.imageUrls].filter(
            Boolean,
          ) as string[],
        ),
      ].slice(0, MAX_IMAGES_PER_GLOBAL_PART);

      if (scrapedImageUrls.length > 0) {
        partData.image_urls = scrapedImageUrls;
      }

      const response = (await sendMessage({
        action: "createPart",
        partData,
      })) as ApiResponse<{ id: string }>;

      if (!response.success && response.status === 409 && response.errorData) {
        const detail = response.errorData;
        const existingId = detail["existing_part_id"];
        const existingName = detail["existing_part_name"];
        const existingSource = detail["existing_part_source"];
        const reason = detail["reason"];
        if (
          typeof existingId === "string" &&
          typeof existingName === "string" &&
          (reason === "non_ugc_exists" || reason === "own_ugc_exists")
        ) {
          setBlockingPart({
            id: existingId,
            name: existingName,
            source:
              typeof existingSource === "string" ? existingSource : "scraped",
            reason,
          });
          setError("");
          setIsLoading(false);
          return;
        }
      }

      if (response.success && response.data?.id) {
        const partId = response.data.id;

        const productUrl = formData.url?.trim() || scrapedData.product_url;
        const retailerForListing =
          retailer ?? (await ensureRetailerForCreate());
        if (
          retailerForListing &&
          productUrl &&
          priceCents != null &&
          priceCents >= 0
        ) {
          const listingResponse = (await sendMessage({
            action: "addPartListing",
            listingData: {
              part_id: partId,
              retailer_id: retailerForListing.id,
              product_url: productUrl,
              price_cents: priceCents,
            },
          })) as ApiResponse<unknown>;

          if (!listingResponse.success) {
            console.warn(
              "Part created but failed to record price:",
              listingResponse.error,
            );
          }
        }

        chrome.storage.sync.get(
          ["openPartAfterCreation", "openInNewTab", "apiUrl"],
          (settings) => {
            const shouldOpen = settings["openPartAfterCreation"] !== false;
            const openInNewTab = settings["openInNewTab"] !== false;

            if (shouldOpen && partId) {
              const apiUrl =
                (settings["apiUrl"] as string) ||
                "https://api.carmodpicker.com/api";
              let frontendUrl = "https://www.carmodpicker.com";

              if (
                apiUrl.includes("localhost") ||
                apiUrl.includes("127.0.0.1")
              ) {
                frontendUrl = "http://localhost:4000";
              } else if (apiUrl.includes("staging")) {
                frontendUrl = "https://staging.carmodpicker.com";
              }

              const partUrl = `${frontendUrl}/parts/${partId}`;

              if (openInNewTab) {
                chrome.tabs.create({ url: partUrl });
              } else {
                chrome.tabs.query(
                  { active: true, currentWindow: true },
                  (tabs) => {
                    if (tabs[0]?.id) {
                      chrome.tabs.update(tabs[0].id, { url: partUrl });
                    }
                  },
                );
              }
            }
          },
        );

        onPartCreated();
      } else {
        setError(response.error || "Failed to create part");
      }
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Failed to create part",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const categoryOptions = categories.map((cat) => ({
    id: cat.id,
    label: cat.display_name || cat.name,
    value: cat.id,
  }));

  const part_manufacturerOptions = useMemo(
    () =>
      part_manufacturers.map((b) => ({
        id: b.id,
        label: b.name,
        value: b.id,
      })),
    [part_manufacturers],
  );

  const carOptions = cars.map((car) => ({
    id: car.id,
    label: `${car.car_make_name} ${car.car_model_name} ${car.generation_name} (${car.start_year}${
      car.end_year ? `-${car.end_year}` : ""
    })`,
    value: car.id,
  }));

  if (viewMode === "checking") {
    return (
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-neutral-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl p-8">
          <p className="text-neutral-300">Checking if part exists...</p>
        </div>
      </div>
    );
  }

  if (viewMode === "record_price" && existingPart) {
    return (
      <RecordPriceDialog
        existingPart={existingPart}
        scrapedData={scrapedData}
        retailer={recordPriceRetailer}
        onClose={onClose}
        onPriceRecorded={onPartCreated}
        sendMessage={sendMessage}
      />
    );
  }

  if (blockingPart) {
    return (
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-neutral-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl w-full max-w-[540px]">
          <div className="flex items-center justify-between p-6 border-b border-white/10">
            <h2 className="text-xl font-bold text-gradient">
              Already in our catalog
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-neutral-400 hover:text-white text-2xl leading-none p-2 hover:bg-white/10 rounded-xl transition-all"
              aria-label="Close dialog"
            >
              &times;
            </button>
          </div>
          <div className="p-6">
            <BlockingPartPanel
              blocking={blockingPart}
              onDismiss={() => setBlockingPart(null)}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-neutral-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl w-full max-w-[800px] max-h-[600px] overflow-y-auto">
        <div className="shrink-0 p-6 border-b border-white/10">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-gradient">Create Part</h2>
            <button
              type="button"
              onClick={onClose}
              className="text-neutral-400 hover:text-white text-2xl leading-none p-2 hover:bg-white/10 rounded-xl transition-all duration-300 hover:scale-110"
              aria-label="Close dialog"
            >
              &times;
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {error && (
            <div className="sticky top-0 z-10 -mx-6 -mt-6 px-6 pt-6 pb-4 bg-neutral-900/95 backdrop-blur-xl">
              <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-xl text-red-200 text-sm">
                {error}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Part Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                required
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <SearchableSelect
                options={part_manufacturerOptions}
                value={formData.part_manufacturerId}
                onChange={(value) => {
                  const id = value !== null && value !== "" ? value : null;
                  setFormData((prev) => ({ ...prev, part_manufacturerId: id }));
                  setPendingPartManufacturerName(null);
                }}
                placeholder="Search or create part_manufacturer..."
                label="PartManufacturer *"
                disabled={isLoading}
                emptyMessage="No part_manufacturers found"
                createNewLabel="Create part_manufacturer"
                displayValue={pendingPartManufacturerName}
                onCreateNew={(text) => {
                  setPendingPartManufacturerName(text.trim());
                  setFormData((prev) => ({ ...prev, part_manufacturerId: null }));
                }}
                filterOptions={async (opts, searchText) => {
                  if (!searchText || searchText.length <= 1) return opts;
                  const results = await searchPartManufacturers(searchText);
                  return results.map((b) => ({
                    id: b.id,
                    label: b.name,
                    value: b.id,
                  }));
                }}
              />
              {pendingPartManufacturerName && (
                <p className="mt-1 text-xs text-neutral-400">
                  New part_manufacturer &quot;{pendingPartManufacturerName}&quot; will be created
                </p>
              )}
            </div>

            {matchedRetailer != null && (
              <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-sm text-neutral-300">
                <span className="font-medium text-neutral-200">Retailer:</span>{" "}
                {matchedRetailer.name}
                {formData.price && (
                  <>
                    {" "}
                    • Price will be recorded for this retailer&apos;s listing
                  </>
                )}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Part Number
              </label>
              <input
                type="text"
                value={formData.partNumber}
                onChange={(e) =>
                  setFormData({ ...formData, partNumber: e.target.value })
                }
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                rows={3}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed resize-y"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Price ($)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.price}
                onChange={(e) =>
                  setFormData({ ...formData, price: e.target.value })
                }
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Product URL
              </label>
              <input
                type="url"
                value={formData.url}
                onChange={(e) =>
                  setFormData({ ...formData, url: e.target.value })
                }
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <SearchableSelect
                options={categoryOptions}
                value={formData.categoryId}
                onChange={(value) =>
                  setFormData({ ...formData, categoryId: value })
                }
                placeholder="Select a category..."
                label="Category *"
                disabled={isLoading}
                emptyMessage="No categories found"
              />
            </div>

            <div>
              <SearchableSelect
                options={carOptions}
                value={formData.carId}
                onChange={(value) =>
                  setFormData({ ...formData, carId: value })
                }
                placeholder="None"
                label="Car Model (Optional)"
                disabled={isLoading}
                emptyMessage="No cars found"
                filterOptions={async (options, searchText) => {
                  if (!searchText || searchText.length <= 2) {
                    return options;
                  }
                  const searchResults = await searchCars(searchText);
                  return searchResults.map((car) => ({
                    id: car.id,
                    label: `${car.car_make_name} ${car.car_model_name} ${
                      car.generation_name
                    } (${car.start_year}${
                      car.end_year ? `-${car.end_year}` : ""
                    })`,
                    value: car.id,
                  }));
                }}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Image URL
                {formData.imageUrls.length > 1
                  ? ` (${formData.imageUrls.length} images from page)`
                  : ""}
              </label>
              <input
                type="url"
                value={formData.imageUrl}
                onChange={(e) =>
                  setFormData({ ...formData, imageUrl: e.target.value })
                }
                placeholder={
                  formData.imageUrls.length > 0
                    ? "Or paste another image URL"
                    : "Product image URL"
                }
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
              {(imagePreview || formData.imageUrls.length > 0) && (
                <div className="mt-3">
                  <p className="text-xs text-neutral-400 mb-2">
                    {formData.imageUrls.length > 1
                      ? `${formData.imageUrls.length} images from page`
                      : "Preview"}
                  </p>
                  <img
                    src={imagePreview || formData.imageUrls[0]}
                    alt="Preview"
                    className="max-w-full max-h-48 rounded-lg border border-white/20 mx-auto"
                    onError={() => setImagePreview("")}
                  />
                  {formData.imageUrls.length > 1 && (
                    <div className="mt-2 flex gap-1 overflow-x-auto pb-1">
                      {formData.imageUrls.slice(0, 10).map((url, i) => (
                        <button
                          key={url}
                          type="button"
                          onClick={() => setImagePreview(url)}
                          className={`shrink-0 w-12 h-12 rounded border overflow-hidden ${
                            (imagePreview || formData.imageUrls[0]) === url
                              ? "border-primary-500 ring-1 ring-primary-500"
                              : "border-white/20 hover:border-white/40"
                          }`}
                        >
                          <img
                            src={url}
                            alt={`Thumbnail ${i + 1}`}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-3 px-6 rounded-xl font-semibold bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white transition-all duration-300 backdrop-blur-[15px] hover:bg-linear-to-br hover:from-white/20 hover:to-white/10 hover:border-white/30 hover:-translate-y-[3px] hover:shadow-[0_10px_25px_rgba(0,0,0,0.2)] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                disabled={isLoading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex-1 py-3 px-6 rounded-xl font-semibold bg-linear-to-r from-[#667eea] to-[#764ba2] bg-size-[200%_200%] text-white border-none transition-all duration-300 hover:translate-y-[-3px] hover:shadow-[0_15px_35px_rgba(102,126,234,0.4)] hover:animate-[gradientShift_3s_ease_infinite] relative overflow-hidden cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                disabled={isLoading}
              >
                {isLoading ? "Creating..." : "Create Part"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default PartDialog;
