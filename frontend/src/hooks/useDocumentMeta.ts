/**
 * Sets document title and meta tags for the active route and restores them on
 * unmount.
 */

import { useEffect } from 'react';

interface DocumentMeta {
  title: string;
  description?: string | undefined;
  canonicalPath?: string | undefined;
}

const SITE_NAME = 'CarModPicker';
const SITE_ORIGIN = 'https://www.carmodpicker.com';
const DEFAULT_DESCRIPTION =
  'CarModPicker helps car enthusiasts discover parts, plan modifications, track build progress, and share their builds with a community of builders.';

function setMetaByName(name: string, content: string) {
  let tag = document.head.querySelector<HTMLMetaElement>(
    `meta[name="${name}"]`
  );
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute('name', name);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content);
}

function setMetaByProperty(property: string, content: string) {
  let tag = document.head.querySelector<HTMLMetaElement>(
    `meta[property="${property}"]`
  );
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute('property', property);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content);
}

function setCanonical(href: string) {
  let tag = document.head.querySelector<HTMLLinkElement>(
    'link[rel="canonical"]'
  );
  if (!tag) {
    tag = document.createElement('link');
    tag.setAttribute('rel', 'canonical');
    document.head.appendChild(tag);
  }
  tag.setAttribute('href', href);
}

/**
 * Sets the document title and the description, canonical and OG tags for the
 * current route. Every route rewrites the same tags, so unmounting needs no
 * reset.
 */
export function useDocumentMeta({
  title,
  description = DEFAULT_DESCRIPTION,
  canonicalPath,
}: DocumentMeta) {
  useEffect(() => {
    const fullTitle = title.includes(SITE_NAME)
      ? title
      : `${title} | ${SITE_NAME}`;
    document.title = fullTitle;

    setMetaByName('description', description);
    setMetaByProperty('og:title', fullTitle);
    setMetaByProperty('og:description', description);
    setMetaByProperty('og:site_name', SITE_NAME);
    setMetaByName('twitter:title', fullTitle);
    setMetaByName('twitter:description', description);

    if (canonicalPath !== undefined) {
      const canonicalUrl = canonicalPath.startsWith('http')
        ? canonicalPath
        : `${SITE_ORIGIN}${canonicalPath.startsWith('/') ? canonicalPath : `/${canonicalPath}`}`;
      setCanonical(canonicalUrl);
      setMetaByProperty('og:url', canonicalUrl);
    }
  }, [title, description, canonicalPath]);
}
