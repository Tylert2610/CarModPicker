import { useCallback, useEffect, useRef, useState } from 'react';

/** One entry in a SearchableSelect: its value and display label. */
export interface SearchableSelectOption {
  id: number | string;
  label: string;
  value: number | string | null;
}

interface SearchableSelectProps {
  options: SearchableSelectOption[];
  value: number | string | null;
  onChange: (value: number | string | null) => void;
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
  ) => SearchableSelectOption[];
  onCreateNew?: (searchText: string) => void | Promise<void>;
  createNewLabel?: string;
  isCreatingNew?: boolean;
  displayValue?: string | null;
  onInputChange?: (text: string) => void;
}

/** A single-select dropdown with type-to-filter and an optional clear button. */
function SearchableSelect({
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
  createNewLabel = 'Create new',
  isCreatingNew = false,
  displayValue,
  onInputChange,
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value) || null;

  const defaultFilterOptions = (
    opts: SearchableSelectOption[],
    text: string
  ): SearchableSelectOption[] => {
    if (!text.trim()) return opts;
    const lowerText = text.toLowerCase();
    return opts.filter((opt) => opt.label.toLowerCase().includes(lowerText));
  };

  const filterOptionsFn = customFilterOptions || defaultFilterOptions;

  const filteredOptions = filterOptionsFn(options, searchText);

  const shouldShowCreateNew =
    onCreateNew &&
    searchText.trim() &&
    filteredOptions.length === 0 &&
    !isLoading &&
    !displayValue;

  useEffect(() => {
    if (displayValue && isOpen) {
      setIsOpen(false);
      setHighlightedIndex(-1);
    }
  }, [displayValue, isOpen]);

  const totalOptions = filteredOptions.length + (shouldShowCreateNew ? 1 : 0);

  const handleSelect = useCallback(
    (selectedValue: number | string | null) => {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, selectedOption, isOpen, displayValue]);

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
          if (
            shouldShowCreateNew &&
            highlightedIndex === filteredOptions.length
          ) {
            void handleCreateNew();
          } else if (filteredOptions[highlightedIndex]) {
            handleSelect(filteredOptions[highlightedIndex].value);
          }
        } else if (shouldShowCreateNew && searchText.trim()) {
          void handleCreateNew();
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, filteredOptions, highlightedIndex, handleSelect]);

  useEffect(() => {
    if (
      highlightedIndex >= 0 &&
      dropdownRef.current &&
      dropdownRef.current.children[highlightedIndex]
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

    if (onInputChange) {
      onInputChange(newText);
    }

    if (!newText.trim()) {
      onChange(null);
    }
  };

  const handleInputFocus = () => {
    setIsOpen(true);
    if (displayValue) {
      setSearchText(displayValue);
    } else if (selectedOption) {
      setSearchText('');
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(null);
    setSearchText('');
    setIsOpen(false);
    inputRef.current?.focus();
  };

  const handleCreateNew = async () => {
    if (onCreateNew && searchText.trim()) {
      await onCreateNew(searchText.trim());
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-foreground mb-2"
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
          onBlur={() => {
            if (displayValue) {
              const currentText = inputRef.current?.value || '';
              if (currentText.trim() === displayValue || !currentText.trim()) {
                setSearchText(displayValue);
              }
            }
          }}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          className="w-full px-5 py-3 bg-gray-800 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-300 ease-out min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed pr-10"
          autoComplete="off"
        />

        {value !== null && value !== '' && !disabled && (
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

      {isOpen && !disabled && !displayValue && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-gray-800 border border-white/20 rounded-xl shadow-lg max-h-60 overflow-auto"
        >
          {isLoading || isCreatingNew ? (
            <div className="px-4 py-3 text-white/60 text-center">
              {isCreatingNew ? 'Creating...' : 'Loading...'}
            </div>
          ) : shouldShowCreateNew ? (
            <>
              <button
                type="button"
                onClick={() => void handleCreateNew()}
                className={`w-full text-left px-4 py-3 hover:bg-gray-700 transition-colors text-primary ${
                  highlightedIndex === filteredOptions.length
                    ? 'bg-gray-700'
                    : ''
                }`}
                onMouseEnter={() => setHighlightedIndex(filteredOptions.length)}
              >
                <span className="flex items-center gap-2">
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
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                  {createNewLabel}: "{searchText}"
                </span>
              </button>
              {filteredOptions.length > 0 && (
                <>
                  <div className="border-t border-white/10 my-1" />
                  {filteredOptions.map((option, index) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => handleSelect(option.value)}
                      className={`w-full text-left px-4 py-3 hover:bg-gray-700 transition-colors ${
                        option.value === value
                          ? 'bg-primary/20 text-primary'
                          : 'text-white'
                      } ${index === highlightedIndex ? 'bg-gray-700' : ''}`}
                      onMouseEnter={() => setHighlightedIndex(index)}
                    >
                      {option.label}
                    </button>
                  ))}
                </>
              )}
            </>
          ) : filteredOptions.length === 0 ? (
            <div className="px-4 py-3 text-white/60 text-center">
              {emptyMessage}
            </div>
          ) : (
            filteredOptions.map((option, index) => (
              <button
                key={option.id}
                type="button"
                onClick={() => handleSelect(option.value)}
                className={`w-full text-left px-4 py-3 hover:bg-gray-700 transition-colors ${
                  option.value === value
                    ? 'bg-primary/20 text-primary'
                    : 'text-white'
                } ${index === highlightedIndex ? 'bg-gray-700' : ''}`}
                onMouseEnter={() => setHighlightedIndex(index)}
              >
                {option.label}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default SearchableSelect;
