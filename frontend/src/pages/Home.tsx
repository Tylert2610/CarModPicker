import { useCallback, useEffect, useState } from 'react';
import { BsTools } from 'react-icons/bs';
import { FaFire, FaUsers } from 'react-icons/fa';
import { GiCarWheel, GiRaceCar } from 'react-icons/gi';
import { Link } from 'react-router-dom';
import BuildListCard from '../components/buildLists/BuildListCard';
import { ErrorAlert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import Spinner from '../components/ui/spinner';
import { HOME_FEATURED_ITEMS_LIMIT } from '../constants';
import useApiRequest from '../hooks/UseApiRequest';
import { useAuth } from '../hooks/useAuth';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import { buildListsApi } from '../api/build_lists';
import { partManufacturersApi } from '../api/part_manufacturers';
import { partsApi } from '../api/parts';
import { retailersApi } from '../api/retailers';
import type { BuildListReadWithVotes } from '../types/Api';

export default function HomePage() {
  useDocumentMeta({
    title: 'CarModPicker | Plan, track, and share your car build',
    description:
      'Discover parts, plan modifications, track build progress, and share your build with the CarModPicker community.',
    canonicalPath: '/',
  });
  const { user, isAuthenticated } = useAuth();
  const [featuredBuildLists, setFeaturedBuildLists] = useState<
    BuildListReadWithVotes[]
  >([]);

  // Fetch featured build lists (top 6 by votes)
  const fetchFeaturedBuildListsFn = useCallback(
    () =>
      buildListsApi.getBuildListsWithVotes({
        limit: HOME_FEATURED_ITEMS_LIMIT,
        skip: 0,
      }),
    []
  );

  const {
    data: featuredBuildListsData,
    isLoading: isLoadingBuildLists,
    error: featuredBuildListsError,
    executeRequest: fetchFeaturedBuildLists,
  } = useApiRequest(fetchFeaturedBuildListsFn);

  // Stats bar: approximate totals for the four stat tiles. Using the /count
  // endpoints (reltuples on Postgres) rather than pagination.total_items so the
  // banner numbers don't force a real COUNT(*) on parts / build_lists.
  const fetchBuildListsCountFn = useCallback(
    () => buildListsApi.countBuildLists(),
    []
  );
  const fetchPartsCountFn = useCallback(() => partsApi.countParts(), []);
  const fetchRetailersCountFn = useCallback(
    () => retailersApi.countRetailers(),
    []
  );
  const fetchPartManufacturersCountFn = useCallback(
    () => partManufacturersApi.countPartManufacturers(),
    []
  );
  const { data: buildListsCountData, executeRequest: fetchBuildListsCount } =
    useApiRequest(fetchBuildListsCountFn);
  const { data: partsCountData, executeRequest: fetchPartsCount } =
    useApiRequest(fetchPartsCountFn);
  const { data: retailersCountData, executeRequest: fetchRetailersCount } =
    useApiRequest(fetchRetailersCountFn);
  const {
    data: partManufacturersCountData,
    executeRequest: fetchPartManufacturersCount,
  } = useApiRequest(fetchPartManufacturersCountFn);

  useEffect(() => {
    void fetchFeaturedBuildLists();
    void fetchBuildListsCount();
    void fetchPartsCount();
    void fetchRetailersCount();
    void fetchPartManufacturersCount();
  }, [
    fetchFeaturedBuildLists,
    fetchBuildListsCount,
    fetchPartsCount,
    fetchRetailersCount,
    fetchPartManufacturersCount,
  ]);

  useEffect(() => {
    if (featuredBuildListsData?.data) {
      // Sort by total votes (upvotes - downvotes) descending
      const sorted = [...featuredBuildListsData.data].sort(
        (a, b) => b.total_votes - a.total_votes
      );
      setFeaturedBuildLists(sorted);
    }
  }, [featuredBuildListsData]);

  return (
    <div className="min-h-screen">
      {/* Landing-page ambient glow — fixed to viewport so it extends behind the ad gutters and persists while scrolling. */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-float"></div>
        <div
          className="absolute bottom-0 left-0 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-float"
          style={{ animationDelay: '1.5s' }}
        ></div>
      </div>

      {/* Compact Hero Section */}
      <section className="relative py-16 px-4">
        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-3xl mx-auto animate-slideInUp">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-primary rounded-xl flex items-center justify-center shadow-2xl animate-glow">
                <GiRaceCar className="text-white text-2xl" />
              </div>
            </div>

            <h1 className="text-4xl md:text-6xl font-bold mb-4 bg-linear-to-r from-white to-primary bg-clip-text text-transparent">
              CarModPicker
            </h1>

            <p className="text-lg md:text-xl text-foreground mb-6 leading-relaxed">
              Discover, plan, and share your car modifications with the
              community
            </p>

            {isAuthenticated && user ? (
              <div className="flex justify-center">
                <Button asChild size="lg">
                  <Link to="/builder">
                    <BsTools />
                    Create Build
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button asChild size="lg">
                  <Link to="/register">
                    <GiRaceCar />
                    Get Started
                  </Link>
                </Button>
                <Button asChild variant="secondary" size="lg">
                  <Link to="/login">Sign In</Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Main Content Grid */}
      <div className="container mx-auto px-4 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Featured Build Lists - Takes 2 columns */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                  <FaFire className="text-white text-lg" />
                </div>
                <h2 className="text-2xl md:text-3xl font-bold text-white">
                  Featured Builds
                </h2>
              </div>
              <Link
                to="/build-lists"
                className="text-primary hover:text-primary/90 transition-colors text-sm font-semibold"
              >
                View All →
              </Link>
            </div>

            {isLoadingBuildLists ? (
              <div className="flex justify-center py-12">
                <Spinner />
              </div>
            ) : featuredBuildListsError ? (
              <Card>
                <ErrorAlert
                  message={`Failed to load featured builds: ${featuredBuildListsError}`}
                />
              </Card>
            ) : featuredBuildLists.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {featuredBuildLists.map((buildList) => (
                  <BuildListCard key={buildList.id} buildList={buildList} />
                ))}
              </div>
            ) : (
              <Card>
                <p className="text-muted-foreground text-center py-8">
                  No featured builds yet. Be the first to create one!
                </p>
              </Card>
            )}
          </div>

          {/* Sidebar - Quick Actions */}
          <div className="space-y-8">
            {/* Quick Actions */}
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-linear-to-br from-success to-primary rounded-lg flex items-center justify-center">
                  <GiCarWheel className="text-white text-lg" />
                </div>
                <h2 className="text-2xl font-bold text-white">Quick Actions</h2>
              </div>
              <div className="space-y-3">
                {isAuthenticated ? (
                  <>
                    <Button
                      asChild
                      variant="secondary"
                      className="w-full justify-start"
                    >
                      <Link to="/builder">
                        <BsTools />
                        Create Build List
                      </Link>
                    </Button>
                    <Button
                      asChild
                      variant="outline"
                      className="w-full justify-start"
                    >
                      <Link to="/build-lists">
                        <FaUsers />
                        Browse Builds
                      </Link>
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      asChild
                      variant="secondary"
                      className="w-full justify-start"
                    >
                      <Link to="/register">
                        <GiRaceCar />
                        Join Free
                      </Link>
                    </Button>
                    <Button
                      asChild
                      variant="outline"
                      className="w-full justify-start"
                    >
                      <Link to="/about">Learn More</Link>
                    </Button>
                  </>
                )}
              </div>
            </div>

            {/* Stats */}
            <Card variant="glass">
              <div className="grid grid-cols-2 gap-6 text-center">
                <div className="animate-slideInUp">
                  <div className="text-3xl font-bold text-primary mb-2">
                    {buildListsCountData?.count ?? '—'}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Build Lists
                  </div>
                </div>
                <div
                  className="animate-slideInUp"
                  style={{ animationDelay: '0.1s' }}
                >
                  <div className="text-3xl font-bold text-primary mb-2">
                    {partsCountData?.count ?? '—'}
                  </div>
                  <div className="text-sm text-muted-foreground">Parts</div>
                </div>
                <div
                  className="animate-slideInUp"
                  style={{ animationDelay: '0.2s' }}
                >
                  <div className="text-3xl font-bold text-primary mb-2">
                    {retailersCountData?.count ?? '—'}
                  </div>
                  <div className="text-sm text-muted-foreground">Retailers</div>
                </div>
                <div
                  className="animate-slideInUp"
                  style={{ animationDelay: '0.3s' }}
                >
                  <div className="text-3xl font-bold text-primary mb-2">
                    {partManufacturersCountData?.count ?? '—'}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Part Manufacturers
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
