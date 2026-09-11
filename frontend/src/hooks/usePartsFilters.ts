import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { LARGE_FETCH_LIMIT } from '../constants';
import { carGenerationsApi } from '../api/car_generations';
import { categoriesApi } from '../api/categories';
import { partManufacturersApi } from '../api/part_manufacturers';
import { partsApi } from '../api/parts';
import type {
  PartManufacturerResponse,
  CarGenerationRead,
  CategoryResponse,
  PaginationInfo,
} from '../types/Api';
import { normalizeCarRead, normalizeCarReadList } from '../utils/carUtils';
import useApiRequest from './UseApiRequest';

const PARTS_PER_PAGE = 100;

export interface UsePartsFiltersOptions {
  /** When set, list and filter-options are scoped to this user (e.g. My Parts). */
  user_id?: string;
  /** When true, filter state is synced to URL and initialized from URL. */
  syncToUrl?: boolean;
}

export interface UsePartsFiltersReturn {
  params: {
    skip: number;
    limit: number;
    category_ids?: string[];
    car_id?: string;
    part_manufacturer_ids?: string[];
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
    user_id?: string;
    universal?: boolean;
  };
  currentPage: number;
  setCurrentPage: (page: number) => void;
  paginationInfo: PaginationInfo | null;
  setPaginationInfo: (info: PaginationInfo | null) => void;

  selectedCategoryIds: string[];
  setSelectedCategoryIds: (ids: string[]) => void;
  selectedPartManufacturerIds: string[];
  setSelectedPartManufacturerIds: (ids: string[]) => void;
  selectedMake: string;
  selectedModel: string;
  selectedGeneration: CarGenerationRead | null;
  setSelectedGeneration: (car: CarGenerationRead | null) => void;
  showUniversalParts: boolean;
  setShowUniversalParts: (v: boolean) => void;
  setSelectedMake: (make: string) => void;
  setSelectedModel: (model: string) => void;
  searchTerm: string;
  setSearchTerm: (s: string) => void;
  priceMin: string;
  priceMax: string;
  setPriceMin: (s: string) => void;
  setPriceMax: (s: string) => void;

  sortParam: string;
  setSortParam: (s?: string) => void;

  categories: CategoryResponse[];
  availableMakes: string[];
  availableCars: CarGenerationRead[];
  availablePartManufacturers: PartManufacturerResponse[];
  activeCategories: CategoryResponse[];
  uniqueModels: string[];
  generations: CarGenerationRead[];
  filterOptions: {
    category_ids: string[];
    part_manufacturer_ids: string[];
    car_ids?: string[];
    make_names?: string[];
  } | null;

  availableCategoryIds: string[];
  availablePartManufacturerIds: string[];
  hasPriceRange: boolean;
  hasActiveFilters: boolean;
  clearAllFilters: () => void;
  clearVehicleFilter: () => void;
  clearPriceRange: () => void;
  toggleCategory: (id: string) => void;
  togglePartManufacturer: (id: string) => void;

  isLoadingMakes: boolean;
  isLoadingCars: boolean;

  isInitializedFromUrl: boolean;
}

export function usePartsFilters(
  options: UsePartsFiltersOptions = {}
): UsePartsFiltersReturn {
  const { user_id: userId, syncToUrl = false } = options;
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] =
    useState<CarGenerationRead | null>(null);
  const [showUniversalParts, setShowUniversalParts] = useState(false);
  const [selectedPartManufacturerIds, setSelectedPartManufacturerIds] =
    useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [priceMin, setPriceMin] = useState<string>('');
  const [priceMax, setPriceMax] = useState<string>('');
  const [sortParam, setSortParamState] = useState<string>('votes_desc');
  const [filterOptions, setFilterOptions] = useState<{
    category_ids: string[];
    part_manufacturer_ids: string[];
    car_ids?: string[];
    make_names?: string[];
  } | null>(null);

  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarGenerationRead[]>([]);
  const [availablePartManufacturers, setAvailablePartManufacturers] = useState<
    PartManufacturerResponse[]
  >([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo | null>(
    null
  );
  const [isInitializedFromUrl, setIsInitializedFromUrl] = useState(false);
  const isInitializingFromUrlRef = useRef(false);

  const fetchMakeStatsFn = useCallback(
    () => carGenerationsApi.getCarMakeStats(),
    []
  );
  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  const fetchCarsByMakeFn = useCallback(
    (make: string) =>
      carGenerationsApi.getCarsByMake(make, { limit: LARGE_FETCH_LIMIT }),
    []
  );
  const {
    data: carsByMake,
    isLoading: isLoadingCars,
    executeRequest: fetchCarsByMake,
  } = useApiRequest(fetchCarsByMakeFn);

  const fetchCarByIdFn = useCallback(
    (carId: string) => carGenerationsApi.getCar(carId),
    []
  );
  const { data: carFromUrl, executeRequest: fetchCarById } =
    useApiRequest(fetchCarByIdFn);

  const loadCategories = useCallback(async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch (error) {
      void error;
    }
  }, []);

  const loadPartManufacturers = useCallback(async () => {
    try {
      const response = await partManufacturersApi.getPartManufacturers(true);
      setAvailablePartManufacturers(response.data);
    } catch (error) {
      void error;
    }
  }, []);

  useEffect(() => {
    void fetchMakes();
    void loadCategories();
    void loadPartManufacturers();
  }, [fetchMakes, loadCategories, loadPartManufacturers]);

  useEffect(() => {
    if (filterOptions?.make_names?.length) {
      setAvailableMakes([...filterOptions.make_names].sort());
    } else if (makeStats) {
      setAvailableMakes(Object.keys(makeStats).sort());
    }
  }, [makeStats, filterOptions?.make_names]);

  useEffect(() => {
    if (
      filterOptions?.make_names?.length &&
      selectedMake &&
      !filterOptions.make_names.includes(selectedMake)
    ) {
      setSelectedMake('');
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [filterOptions?.make_names, selectedMake]);

  useEffect(() => {
    const list = normalizeCarReadList(carsByMake ?? undefined);
    if (filterOptions?.car_ids?.length) {
      const allowed = new Set(filterOptions.car_ids);
      setAvailableCars(list.filter((c) => c.id != null && allowed.has(c.id)));
    } else {
      setAvailableCars(list);
    }
  }, [carsByMake, filterOptions?.car_ids]);

  const generations = useMemo(
    () =>
      availableCars
        .filter(
          (c) =>
            (c.car_make_name ?? '') === selectedMake &&
            (c.car_model_name ?? '') === selectedModel
        )
        .sort((a, b) => {
          if (a.start_year !== b.start_year) return a.start_year - b.start_year;
          return (a.generation_name ?? '').localeCompare(
            b.generation_name ?? ''
          );
        }),
    [availableCars, selectedMake, selectedModel]
  );

  /** Car IDs for API filter: single generation, or all for make, or all for make+model */
  const effectiveCarIds = useMemo(
    () =>
      selectedGeneration
        ? [selectedGeneration.id]
        : selectedModel
          ? generations.map((c) => c.id)
          : selectedMake
            ? availableCars.map((c) => c.id)
            : [],
    [
      selectedGeneration,
      selectedModel,
      selectedMake,
      generations,
      availableCars,
    ]
  );

  const filterOptionsRequestKey = `${selectedCategoryIds.join(',')}-${selectedPartManufacturerIds.join(',')}-${showUniversalParts}-${effectiveCarIds.join(',')}-${searchTerm}-${userId ?? ''}`;

  useEffect(() => {
    let cancelled = false;
    const filterOptionsParams: Parameters<typeof partsApi.getFilterOptions>[0] =
      {};
    if (selectedCategoryIds.length > 0)
      filterOptionsParams.category_ids = selectedCategoryIds;
    if (selectedPartManufacturerIds.length > 0)
      filterOptionsParams.part_manufacturer_ids = selectedPartManufacturerIds;
    if (effectiveCarIds.length && !showUniversalParts)
      filterOptionsParams.car_ids = effectiveCarIds;
    if (showUniversalParts) filterOptionsParams.universal = true;
    if (searchTerm.trim()) filterOptionsParams.search = searchTerm;
    if (userId !== undefined) filterOptionsParams.user_id = userId;
    void partsApi
      .getFilterOptions(filterOptionsParams)
      .then((res) => {
        if (!cancelled) setFilterOptions(res.data);
      })
      .catch(() => {
        if (!cancelled) setFilterOptions(null);
      });
    return () => {
      cancelled = true;
    };
  }, [filterOptionsRequestKey]); // eslint-disable-line react-hooks/exhaustive-deps -- intentionally only refetch when request key changes

  const initializeFromUrl = useCallback(() => {
    if (
      !syncToUrl ||
      isInitializedFromUrl ||
      !makeStats ||
      !categories.length ||
      !availablePartManufacturers.length
    ) {
      return;
    }
    const hasUrlParams = Array.from(searchParams.keys()).length > 0;
    if (!hasUrlParams) {
      setIsInitializedFromUrl(true);
      return;
    }
    const categoryIdParams = searchParams.getAll('category_ids');
    const categoryIdsRaw =
      categoryIdParams.length > 0
        ? categoryIdParams
        : searchParams.get('category_id')
          ? [searchParams.get('category_id') as string]
          : [];
    if (categoryIdsRaw.length > 0) {
      const valid = categoryIdsRaw.filter((id) =>
        categories.some((c) => c.id === id)
      );
      if (valid.length > 0) setSelectedCategoryIds(valid);
    }
    const part_manufacturerIdParams = searchParams.getAll(
      'part_manufacturer_ids'
    );
    const part_manufacturerIdsRaw =
      part_manufacturerIdParams.length > 0
        ? part_manufacturerIdParams
        : searchParams.get('part_manufacturer_id')
          ? [searchParams.get('part_manufacturer_id') as string]
          : [];
    if (part_manufacturerIdsRaw.length > 0) {
      const valid = part_manufacturerIdsRaw.filter((id) =>
        availablePartManufacturers.some((b) => b.id === id)
      );
      if (valid.length > 0) setSelectedPartManufacturerIds(valid);
    }
    const carIdParam = searchParams.get('car_id');
    if (carIdParam) {
      isInitializingFromUrlRef.current = true;
      void fetchCarById(carIdParam);
      return;
    }
    if (searchParams.get('universal') === 'true') setShowUniversalParts(true);
    const makeParam = searchParams.get('make');
    const modelParam = searchParams.get('model');
    if (makeParam && availableMakes.includes(makeParam)) {
      setSelectedMake(makeParam);
      if (modelParam) {
        isInitializingFromUrlRef.current = true;
        void fetchCarsByMake(makeParam);
      }
    }
    const searchParam = searchParams.get('search');
    if (searchParam) setSearchTerm(searchParam);
    const minPriceParam = searchParams.get('min_price');
    if (minPriceParam !== null && minPriceParam !== '') {
      const n = Number.parseFloat(minPriceParam);
      if (!Number.isNaN(n) && n >= 0) setPriceMin(minPriceParam);
    }
    const maxPriceParam = searchParams.get('max_price');
    if (maxPriceParam !== null && maxPriceParam !== '') {
      const n = Number.parseFloat(maxPriceParam);
      if (!Number.isNaN(n) && n >= 0) setPriceMax(maxPriceParam);
    }
    const pageParam = searchParams.get('page');
    if (pageParam) {
      const page = Number.parseInt(pageParam, 10);
      if (!Number.isNaN(page) && page > 0) setCurrentPage(page);
    }
    const sortParamFromUrl = searchParams.get('sort');
    if (sortParamFromUrl) setSortParamState(sortParamFromUrl);
    setIsInitializedFromUrl(true);
  }, [
    syncToUrl,
    searchParams,
    makeStats,
    categories,
    availablePartManufacturers,
    availableMakes,
    isInitializedFromUrl,
    fetchCarById,
    fetchCarsByMake,
  ]);

  useEffect(() => {
    if (syncToUrl) void initializeFromUrl();
  }, [syncToUrl, initializeFromUrl]);

  useEffect(() => {
    if (carFromUrl && isInitializingFromUrlRef.current) {
      const car = normalizeCarRead(carFromUrl);
      if (car) {
        setSelectedMake(car.car_make_name);
        setSelectedModel(car.car_model_name);
        setSelectedGeneration(car);
        setShowUniversalParts(false);
        void fetchCarsByMake(car.car_make_name);
      }
      isInitializingFromUrlRef.current = false;
      setIsInitializedFromUrl(true);
    }
  }, [carFromUrl, fetchCarsByMake]);

  useEffect(() => {
    if (
      syncToUrl &&
      selectedMake &&
      carsByMake?.length &&
      searchParams.get('model') &&
      !selectedGeneration
    ) {
      const carIdParam = searchParams.get('car_id');
      if (carIdParam) {
        const car = normalizeCarRead(
          carsByMake.find((c) => c.id === carIdParam) ?? null
        );
        if (car) setSelectedGeneration(car);
      } else {
        setSelectedModel(searchParams.get('model') ?? '');
      }
      setIsInitializedFromUrl(true);
    }
  }, [syncToUrl, selectedMake, carsByMake, searchParams, selectedGeneration]);

  useEffect(() => {
    if (selectedMake && !isInitializingFromUrlRef.current) {
      void fetchCarsByMake(selectedMake);
      if (
        !selectedGeneration ||
        (selectedGeneration.car_make_name ?? '') !== selectedMake
      ) {
        setSelectedModel('');
        setSelectedGeneration(null);
      }
    } else if (!showUniversalParts && !selectedMake) {
      setAvailableCars([]);
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [selectedMake, selectedGeneration, fetchCarsByMake, showUniversalParts]);

  const syncFiltersToUrl = useCallback(() => {
    if (!syncToUrl || !isInitializedFromUrl) return;
    const newParams = new URLSearchParams();
    selectedCategoryIds.forEach((id) =>
      newParams.append('category_ids', id.toString())
    );
    selectedPartManufacturerIds.forEach((id) =>
      newParams.append('part_manufacturer_ids', id.toString())
    );
    if (showUniversalParts) newParams.set('universal', 'true');
    else if (selectedGeneration)
      newParams.set('car_id', selectedGeneration.id.toString());
    else if (selectedMake) {
      newParams.set('make', selectedMake);
      if (selectedModel) newParams.set('model', selectedModel);
    }
    if (searchTerm) newParams.set('search', searchTerm);
    if (priceMin.trim() !== '') {
      const n = Number.parseFloat(priceMin.trim());
      if (!Number.isNaN(n) && n >= 0)
        newParams.set('min_price', priceMin.trim());
    }
    if (priceMax.trim() !== '') {
      const n = Number.parseFloat(priceMax.trim());
      if (!Number.isNaN(n) && n >= 0)
        newParams.set('max_price', priceMax.trim());
    }
    if (currentPage > 1) newParams.set('page', currentPage.toString());
    if (sortParam && sortParam !== 'votes_desc')
      newParams.set('sort', sortParam);
    const next = newParams.toString();
    if (searchParams.toString() === next) return;
    setSearchParams(newParams, { replace: true });
  }, [
    syncToUrl,
    isInitializedFromUrl,
    selectedCategoryIds,
    selectedPartManufacturerIds,
    showUniversalParts,
    selectedGeneration,
    selectedMake,
    selectedModel,
    searchTerm,
    priceMin,
    priceMax,
    currentPage,
    sortParam,
    searchParams,
    setSearchParams,
  ]);

  useEffect(() => {
    if (syncToUrl && isInitializedFromUrl) syncFiltersToUrl();
  }, [
    syncToUrl,
    isInitializedFromUrl,
    selectedCategoryIds,
    selectedPartManufacturerIds,
    showUniversalParts,
    selectedGeneration,
    selectedMake,
    selectedModel,
    searchTerm,
    priceMin,
    priceMax,
    currentPage,
    sortParam,
    syncFiltersToUrl,
  ]);

  useEffect(() => {
    if (!syncToUrl || !isInitializedFromUrl) return;
    const t = setTimeout(syncFiltersToUrl, 500);
    return () => clearTimeout(t);
  }, [syncToUrl, searchTerm, syncFiltersToUrl, isInitializedFromUrl]);

  useEffect(() => {
    setCurrentPage(1);
  }, [
    selectedCategoryIds,
    effectiveCarIds,
    showUniversalParts,
    selectedPartManufacturerIds,
    searchTerm,
    priceMin,
    priceMax,
    sortParam,
  ]);

  const uniqueModels = useMemo(
    () =>
      Array.from(
        new Set(
          availableCars.map((c) => c.car_model_name ?? '').filter(Boolean)
        )
      ).sort(),
    [availableCars]
  );

  const activeCategories = useMemo(
    () =>
      categories
        .filter((c) => c.is_active)
        .sort((a, b) => a.sort_order - b.sort_order),
    [categories]
  );

  const availableCategoryIds = useMemo(
    () => filterOptions?.category_ids ?? activeCategories.map((c) => c.id),
    [filterOptions?.category_ids, activeCategories]
  );

  const availablePartManufacturerIds = useMemo(
    () =>
      filterOptions?.part_manufacturer_ids ??
      availablePartManufacturers.map((b) => b.id),
    [filterOptions?.part_manufacturer_ids, availablePartManufacturers]
  );

  const hasPriceRange =
    (priceMin.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(priceMin.trim())) &&
      Number.parseFloat(priceMin.trim()) >= 0) ||
    (priceMax.trim() !== '' &&
      !Number.isNaN(Number.parseFloat(priceMax.trim())) &&
      Number.parseFloat(priceMax.trim()) >= 0);

  const hasActiveFilters =
    selectedCategoryIds.length > 0 ||
    selectedPartManufacturerIds.length > 0 ||
    effectiveCarIds.length > 0 ||
    showUniversalParts ||
    hasPriceRange;

  const toggleCategory = useCallback((categoryId: string) => {
    setSelectedCategoryIds((prev) =>
      prev.includes(categoryId)
        ? prev.filter((id) => id !== categoryId)
        : [...prev, categoryId]
    );
  }, []);

  const togglePartManufacturer = useCallback((part_manufacturerId: string) => {
    setSelectedPartManufacturerIds((prev) =>
      prev.includes(part_manufacturerId)
        ? prev.filter((id) => id !== part_manufacturerId)
        : [...prev, part_manufacturerId]
    );
  }, []);

  const clearAllFilters = useCallback(() => {
    setSelectedCategoryIds([]);
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
    setShowUniversalParts(false);
    setSelectedPartManufacturerIds([]);
    setSearchTerm('');
    setPriceMin('');
    setPriceMax('');
    setCurrentPage(1);
  }, []);

  const clearVehicleFilter = useCallback(() => {
    setShowUniversalParts(false);
    setSelectedMake('');
    setSelectedModel('');
    setSelectedGeneration(null);
  }, []);

  const clearPriceRange = useCallback(() => {
    setPriceMin('');
    setPriceMax('');
  }, []);

  const setSortParam = useCallback((s?: string) => {
    if (s !== undefined) {
      setSortParamState(s);
      setCurrentPage(1);
    }
  }, []);

  const params = useMemo(() => {
    const minCents =
      priceMin.trim() !== ''
        ? Math.round(Number.parseFloat(priceMin.trim()) * 100)
        : undefined;
    const maxCents =
      priceMax.trim() !== ''
        ? Math.round(Number.parseFloat(priceMax.trim()) * 100)
        : undefined;
    const min_price_cents =
      minCents !== undefined && !Number.isNaN(minCents) && minCents >= 0
        ? minCents
        : undefined;
    const max_price_cents =
      maxCents !== undefined && !Number.isNaN(maxCents) && maxCents >= 0
        ? maxCents
        : undefined;
    return {
      skip: (currentPage - 1) * PARTS_PER_PAGE,
      limit: PARTS_PER_PAGE,
      ...(userId !== undefined && { user_id: userId }),
      ...(selectedCategoryIds.length > 0 && {
        category_ids: selectedCategoryIds,
      }),
      ...(effectiveCarIds.length &&
        !showUniversalParts && { car_ids: effectiveCarIds }),
      ...(showUniversalParts && { universal: true }),
      ...(selectedPartManufacturerIds.length > 0 && {
        part_manufacturer_ids: selectedPartManufacturerIds,
      }),
      ...(searchTerm && { search: searchTerm }),
      ...(sortParam && { sort: sortParam }),
      ...(min_price_cents !== undefined && { min_price_cents }),
      ...(max_price_cents !== undefined && { max_price_cents }),
    };
  }, [
    currentPage,
    userId,
    selectedCategoryIds,
    effectiveCarIds,
    showUniversalParts,
    selectedPartManufacturerIds,
    searchTerm,
    sortParam,
    priceMin,
    priceMax,
  ]);

  return {
    params,
    currentPage,
    setCurrentPage,
    paginationInfo,
    setPaginationInfo,
    selectedCategoryIds,
    setSelectedCategoryIds,
    selectedPartManufacturerIds,
    setSelectedPartManufacturerIds,
    selectedMake,
    selectedModel,
    selectedGeneration,
    setSelectedGeneration,
    showUniversalParts,
    setShowUniversalParts,
    setSelectedMake,
    setSelectedModel,
    searchTerm,
    setSearchTerm,
    priceMin,
    priceMax,
    setPriceMin,
    setPriceMax,
    sortParam,
    setSortParam,
    categories,
    availableMakes,
    availableCars,
    availablePartManufacturers,
    activeCategories,
    uniqueModels,
    generations,
    filterOptions,
    availableCategoryIds,
    availablePartManufacturerIds,
    hasPriceRange,
    hasActiveFilters,
    clearAllFilters,
    clearVehicleFilter,
    clearPriceRange,
    toggleCategory,
    togglePartManufacturer,
    isLoadingMakes,
    isLoadingCars,
    isInitializedFromUrl,
  };
}

export const GLOBAL_PARTS_PARTS_PER_PAGE = PARTS_PER_PAGE;
