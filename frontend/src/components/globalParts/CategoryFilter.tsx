import React from 'react';
import type { CategoryResponse } from '../../types/Api';

interface CategoryFilterProps {
  categories: CategoryResponse[];
  selectedCategory: number | null;
  onCategoryChange: (categoryId: number | null) => void;
}

const CategoryFilter: React.FC<CategoryFilterProps> = ({
  categories,
  selectedCategory,
  onCategoryChange,
}) => {
  return (
    <div className="relative">
      <select
        value={selectedCategory || ''}
        onChange={(e) =>
          onCategoryChange(e.target.value ? Number(e.target.value) : null)
        }
        className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        <option value="">All Categories</option>
        {categories
          .filter((category) => category.is_active)
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((category) => (
            <option key={category.id} value={category.id}>
              {category.display_name}
            </option>
          ))}
      </select>
    </div>
  );
};

export default CategoryFilter;
