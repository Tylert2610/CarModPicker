import React from 'react';
import { Link } from 'react-router-dom';
import { FaArrowUp } from 'react-icons/fa';
import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import { Card } from '../ui/card';
import type { BuildListRead, BuildListReadWithVotes } from '../../types/Api';

interface BuildListCardProps {
  buildList: BuildListRead | BuildListReadWithVotes;
}

/** Narrows a build list to the variant that carries vote tallies. */
function hasVoteData(
  bl: BuildListRead | BuildListReadWithVotes
): bl is BuildListReadWithVotes {
  return 'total_votes' in bl && typeof bl.total_votes === 'number';
}

/** Cents as a dollar amount with two decimal places. */
function formatTotalCost(cents: number): string {
  return `$${(cents / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/** A build list as an image-led card, with its vote badge and total cost. */
const BuildListCard: React.FC<BuildListCardProps> = ({ buildList }) => {
  const showVoteBadge = hasVoteData(buildList);
  const totalVotes = showVoteBadge ? buildList.total_votes : 0;
  const totalCostCents =
    hasVoteData(buildList) && typeof buildList.total_cost_cents === 'number'
      ? buildList.total_cost_cents
      : null;

  return (
    <Link
      to={`/build-lists/${buildList.id}`}
      className="block hover:no-underline"
    >
      <Card className="h-full hover:border-primary border-2 border-transparent transition-all duration-300 group">
        <div className="relative mb-4">
          <ImageWithPlaceholder
            srcUrl={buildList.image_urls?.[0] ?? null}
            altText={buildList.name}
            imageClassName="w-full h-full object-cover rounded-lg group-hover:scale-105 transition-transform duration-300"
            containerClassName="w-full aspect-video"
            fallbackText="No image"
          />
          {showVoteBadge && (
            <div className="absolute top-3 right-3 flex items-center gap-1 bg-black/60 backdrop-blur-sm px-2 py-1 rounded-lg">
              <FaArrowUp className="text-primary text-xs" />
              <span className="text-xs font-semibold text-white">
                {totalVotes} votes
              </span>
            </div>
          )}
          {totalCostCents != null && totalCostCents > 0 && (
            <div className="absolute bottom-3 left-3 flex items-center bg-black/60 backdrop-blur-sm px-2 py-1 rounded-lg">
              <span className="text-sm font-semibold text-green-400">
                {formatTotalCost(totalCostCents)} total
              </span>
            </div>
          )}
        </div>
        <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-primary transition-colors">
          {buildList.name}
        </h3>
        {buildList.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {buildList.description}
          </p>
        )}
      </Card>
    </Link>
  );
};

export default BuildListCard;
