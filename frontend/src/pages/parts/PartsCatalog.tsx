import React, { useState, useEffect } from 'react';
import { partsApi, categoriesApi } from '../../services/Api';
import { PartReadWithVotes, CategoryResponse } from '../../types/Api';
import Card from '../../components/common/Card';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import VoteButtons from '../../components/parts/VoteButtons';
import CategoryFilter from '../../components/parts/CategoryFilter';
import PageHeader from '../../components/layout/PageHeader';

const PartsCatalog: React.FC = () => {
  const [parts, setParts] = useState<PartReadWithVotes[]>([]);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const itemsPerPage = 20;

  useEffect(() => {
    loadCategories();
    loadParts();
  }, []);

  useEffect(() => {
    setCurrentPage(1);
    loadParts();
  }, [searchTerm, selectedCategory]);

  const loadCategories = async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  };

  const loadParts = async (page = 1) => {
    try {
      setLoading(true);
      const params = {
        skip: (page - 1) * itemsPerPage,
        limit: itemsPerPage,
        category_id: selectedCategory || undefined,
        search: searchTerm || undefined,
      };

      const response = await partsApi.getPartsWithVotes(params);

      if (page === 1) {
        setParts(response.data);
      } else {
        setParts((prev) => [...prev, ...response.data]);
      }

      setHasMore(response.data.length === itemsPerPage);
      setCurrentPage(page);
    } catch (error) {
      console.error('Failed to load parts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadMore = () => {
    if (!loading && hasMore) {
      loadParts(currentPage + 1);
    }
  };

  const handleVoteUpdate = (
    partId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => {
    setParts((prev) =>
      prev.map((part) => {
        if (part.id === partId) {
          const currentVote = part.user_vote;
          let upvotes = part.upvotes;
          let downvotes = part.downvotes;

          // Remove previous vote
          if (currentVote === 'upvote') upvotes--;
          if (currentVote === 'downvote') downvotes--;

          // Add new vote
          if (newVote === 'upvote') upvotes++;
          if (newVote === 'downvote') downvotes++;

          return {
            ...part,
            upvotes,
            downvotes,
            total_votes: upvotes + downvotes,
            user_vote: newVote,
          };
        }
        return part;
      })
    );
  };

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedCategory(null);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <PageHeader title="Parts Catalog" />

      <div className="container mx-auto px-4 py-8">
        {/* Filters */}
        <div className="mb-8 space-y-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <Input
                type="text"
                placeholder="Search parts..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full"
              />
            </div>
            <CategoryFilter
              categories={categories}
              selectedCategory={selectedCategory}
              onCategoryChange={setSelectedCategory}
            />
            <button
              onClick={clearFilters}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              Clear Filters
            </button>
          </div>
        </div>

        {/* Parts Grid */}
        {loading && parts.length === 0 ? (
          <div className="flex justify-center items-center h-64">
            <LoadingSpinner />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {parts.map((part) => (
                <Card
                  key={part.id}
                  className="hover:shadow-lg transition-shadow"
                >
                  <div className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-lg font-semibold text-white truncate">
                        {part.name}
                      </h3>
                      {part.is_verified && (
                        <span className="text-green-400 text-sm">
                          ✓ Verified
                        </span>
                      )}
                    </div>

                    {part.image_url && (
                      <img
                        src={part.image_url}
                        alt={part.name}
                        className="w-full h-32 object-cover rounded-lg mb-3"
                      />
                    )}

                    {part.description && (
                      <p className="text-gray-300 text-sm mb-3 line-clamp-2">
                        {part.description}
                      </p>
                    )}

                    <div className="flex items-center justify-between mb-3">
                      {part.brand && (
                        <span className="text-blue-400 text-sm">
                          {part.brand}
                        </span>
                      )}
                      {part.price && (
                        <span className="text-green-400 font-semibold">
                          ${part.price.toLocaleString()}
                        </span>
                      )}
                    </div>

                    <VoteButtons
                      partId={part.id}
                      upvotes={part.upvotes}
                      downvotes={part.downvotes}
                      userVote={part.user_vote}
                      onVoteUpdate={handleVoteUpdate}
                    />

                    <div className="mt-3 pt-3 border-t border-gray-700">
                      <div className="flex items-center justify-between text-xs text-gray-400">
                        <span>
                          Category:{' '}
                          {
                            categories.find((c) => c.id === part.category_id)
                              ?.display_name
                          }
                        </span>
                        <span>
                          Created:{' '}
                          {new Date(part.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>

            {/* Load More Button */}
            {hasMore && (
              <div className="flex justify-center mt-8">
                <button
                  onClick={handleLoadMore}
                  disabled={loading}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded-lg transition-colors"
                >
                  {loading ? <LoadingSpinner size="sm" /> : 'Load More'}
                </button>
              </div>
            )}

            {!hasMore && parts.length > 0 && (
              <div className="text-center mt-8 text-gray-400">
                No more parts to load
              </div>
            )}
          </>
        )}

        {!loading && parts.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-400 text-lg">No parts found</p>
            <p className="text-gray-500 mt-2">
              Try adjusting your search or filters
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default PartsCatalog;
