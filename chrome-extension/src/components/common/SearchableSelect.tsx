import React, { useState, useEffect, useRef, useCallback } from 'react';

export interface SearchableSelectOption {
  id: string;
  label: string;
  value: string | null;
}

interface SearchableSelectProps {
  options: SearchableSelectOption[];
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
  label?: string;
  id?: string;
  name?: string;
  disabled?: boolean;
  isLoading?: boolean;
  emptyMessage?: string;
  filterOptions?: (
    options: SearchableSelectOption[],
    searchText: string
  ) => SearchableSelectOption[] | Promise<SearchableSelectOption[]>;
  /** When provided, show "Create X" option when no matches. Called when user selects it. */
  onCreateNew?: (searchText: string) => void | Promise<void>;
  createNewLabel?: string;
  /** Display text when value is null (e.g. pending part_manufacturer creation) */
  displayValue?: string | null;
}

/** Text input with a filtered dropdown, keyboard navigation and optional create. */
const SearchableSelect: React.FC<SearchableSelectProps> = ({
  options,
  value,
  onChange,
  placeholder = 'Type to search...',
  label,
  id,
  name,
  disabled = false,
  isLoading = false,
  emptyMessage = 'No options found',
  filterOptions: customFilterOptions,
  onCreateNew,
  createNewLabel = 'Create',
  displayValue,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [filteredOptions, setFilteredOptions] = useState<SearchableSelectOption[]>(options);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value) || null;

  const shouldShowCreateNew =
    onCreateNew &&
    searchText.trim() &&
    filteredOptions.length === 0 &&
    !isLoading &&
    !displayValue;
  const totalOptions = filteredOptions.length + (shouldShowCreateNew ? 1 : 0);

  const defaultFilterOptions = useCallback(
    (opts: SearchableSelectOption[], text: string): SearchableSelectOption[] => {
      if (!text.trim()) return opts;
      const lowerText = text.toLowerCase();
      return opts.filter((opt) => opt.label.toLowerCase().includes(lowerText));
    },
    []
  );

  useEffect(() => {
    const filterFn = customFilterOptions || defaultFilterOptions;
    const filter = async () => {
      const result = filterFn(options, searchText);
      if (result instanceof Promise) {
        const resolved = await result;
        setFilteredOptions(resolved);
      } else {
        setFilteredOptions(result);
      }
    };
    filter();
  }, [searchText, options, customFilterOptions, defaultFilterOptions]);

  const handleSelect = useCallback(
    (selectedValue: string | null) => {
      onChange(selectedValue);
      setIsOpen(false);
      setHighlightedIndex(-1);
      const option = options.find((opt) => opt.value === selectedValue);
      if (option) {
        setSearchText(option.label);
      } else {
        setSearchText('');
      }
      inputRef.current?.blur();
    },
    [onChange, options]
  );

  useEffect(() => {
    if (displayValue) {
      setSearchText(displayValue);
    } else if (value === null || value === '') {
      setSearchText('');
    } else if (selectedOption && searchText !== selectedOption.label) {
      if (!isOpen) {
        setSearchText(selectedOption.label);
      }
    }
  }, [value, selectedOption, isOpen, displayValue]);

  const handleCreateNew = useCallback(() => {
    const text = searchText.trim();
    if (text && onCreateNew) {
      void onCreateNew(text);
      setIsOpen(false);
      setHighlightedIndex(-1);
    }
  }, [searchText, onCreateNew]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setHighlightedIndex(-1);
        if (selectedOption) {
          setSearchText(selectedOption.label);
        } else if (displayValue) {
          setSearchText(displayValue);
        } else {
          setSearchText('');
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [selectedOption, displayValue]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev < totalOptions - 1 ? prev + 1 : prev
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : -1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (highlightedIndex >= 0) {
          if (shouldShowCreateNew && highlightedIndex === filteredOptions.length) {
            handleCreateNew();
          } else if (filteredOptions[highlightedIndex]) {
            const opt = filteredOptions[highlightedIndex];
            if (opt) handleSelect(opt.value);
          }
        } else if (shouldShowCreateNew && searchText.trim()) {
          handleCreateNew();
        }
      } else if (e.key === 'Escape') {
        setIsOpen(false);
        setHighlightedIndex(-1);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, filteredOptions, highlightedIndex, handleSelect, shouldShowCreateNew, searchText, handleCreateNew, totalOptions]);

  useEffect(() => {
    if (
        highlightedIndex >= 0 &&
        dropdownRef.current &&
        dropdownRef.current.children[highlightedIndex] &&
        highlightedIndex < totalOptions
    ) {
      const optionElement = dropdownRef.current.children[
        highlightedIndex
      ] as HTMLElement;
      if (optionElement) {
        optionElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightedIndex]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newText = e.target.value;
    setSearchText(newText);
    setIsOpen(true);
    setHighlightedIndex(-1);

    if (!newText.trim()) {
      onChange(null);
    }
  };

  const handleInputFocus = () => {
    setIsOpen(true);
    if (selectedOption) {
      setSearchText('');
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(null);
    setSearchText('');
    setIsOpen(false);
    setHighlightedIndex(-1);
    inputRef.current?.focus();
  };

  return (
    <div className="relative" ref={containerRef}>
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-neutral-300 mb-2"
        >
          {label}
        </label>
      )}

      <div className="relative">
        <input
          ref={inputRef}
          id={id}
          name={name}
          type="text"
          value={searchText}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          className="w-full px-5 py-4 pr-10 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
          autoComplete="off"
        />

        {((value !== null && value !== '') || displayValue) && !disabled && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-white/60 hover:text-white transition-colors"
            tabIndex={-1}
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}

        {!value && (
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none text-white/60">
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        )}
      </div>

      {isOpen && !disabled && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-gray-800 border border-white/20 rounded-xl shadow-lg max-h-60 overflow-auto"
        >
          {isLoading ? (
            <div className="px-4 py-3 text-white/60 text-center">Loading...</div>
          ) : filteredOptions.length === 0 && !shouldShowCreateNew ? (
            <div className="px-4 py-3 text-white/60 text-center">{emptyMessage}</div>
          ) : (
            <>
              {filteredOptions.map((option, index) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => handleSelect(option.value)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-700 transition-colors ${
                    option.value === value
                      ? 'bg-primary-500/20 text-primary-400'
                      : 'text-white'
                  } ${index === highlightedIndex ? 'bg-gray-700' : ''}`}
                  onMouseEnter={() => setHighlightedIndex(index)}
                >
                  {option.label}
                </button>
              ))}
              {shouldShowCreateNew && (
                <button
                  type="button"
                  onClick={handleCreateNew}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-700 transition-colors text-primary-400 ${
                    filteredOptions.length === highlightedIndex ? 'bg-gray-700' : ''
                  }`}
                  onMouseEnter={() => setHighlightedIndex(filteredOptions.length)}
                >
                  {createNewLabel} &quot;{searchText.trim()}&quot;
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchableSelect;
