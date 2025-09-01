import React, { useState } from 'react';
import { globalPartVotesApi } from '../../services/Api';

interface VoteButtonsProps {
  partId: number;
  upvotes: number;
  downvotes: number;
  userVote?: 'upvote' | 'downvote' | null;
  onVoteUpdate: (partId: number, newVote: 'upvote' | 'downvote' | null) => void;
  size?: 'sm' | 'md' | 'lg';
}

const VoteButtons: React.FC<VoteButtonsProps> = ({
  partId,
  upvotes,
  downvotes,
  userVote,
  onVoteUpdate,
  size = 'md',
}) => {
  const [isVoting, setIsVoting] = useState(false);
  const [localUpvotes, setLocalUpvotes] = useState(upvotes);
  const [localDownvotes, setLocalDownvotes] = useState(downvotes);
  const [localUserVote, setLocalUserVote] = useState(userVote);

  const handleVote = async (voteType: 'upvote' | 'downvote') => {
    if (isVoting) return;

    try {
      setIsVoting(true);

      // Optimistic update - immediately update the UI
      let newUpvotes = localUpvotes;
      let newDownvotes = localDownvotes;
      let newUserVote: 'upvote' | 'downvote' | null = localUserVote || null;

      // Remove previous vote if it exists
      if (localUserVote === 'upvote') {
        newUpvotes -= 1;
      } else if (localUserVote === 'downvote') {
        newDownvotes -= 1;
      }

      // If user already voted the same way, remove the vote
      if (localUserVote === voteType) {
        newUserVote = null;
      } else {
        // Otherwise, vote or change vote
        newUserVote = voteType;
        if (voteType === 'upvote') {
          newUpvotes += 1;
        } else {
          newDownvotes += 1;
        }
      }

      // Update local state immediately
      setLocalUpvotes(newUpvotes);
      setLocalDownvotes(newDownvotes);
      setLocalUserVote(newUserVote);

      // Make the API call
      if (localUserVote === voteType) {
        await globalPartVotesApi.removeVote(partId);
        onVoteUpdate(partId, null);
      } else {
        await globalPartVotesApi.voteOnGlobalPart(partId, {
          vote_type: voteType,
        });
        onVoteUpdate(partId, voteType);
      }
    } catch (error) {
      console.error('Failed to vote:', error);
      // Revert optimistic update on error
      setLocalUpvotes(upvotes);
      setLocalDownvotes(downvotes);
      setLocalUserVote(userVote);
      // You might want to show a toast notification here
    } finally {
      setIsVoting(false);
    }
  };

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'text-sm';
      case 'lg':
        return 'text-lg';
      default:
        return 'text-base';
    }
  };

  const getButtonSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'p-1';
      case 'lg':
        return 'p-3';
      default:
        return 'p-2';
    }
  };

  const totalVotes = localUpvotes - localDownvotes;

  return (
    <div className={`flex items-center space-x-2 ${getSizeClasses()}`}>
      {/* Upvote Button */}
      <button
        type="button"
        onClick={() => {
          void handleVote('upvote');
        }}
        disabled={isVoting}
        className={`
          ${getButtonSizeClasses()}
          rounded-lg transition-colors duration-200
          ${
            localUserVote === 'upvote'
              ? 'bg-green-600 text-white hover:bg-green-700'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white'
          }
          ${isVoting ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        title="Upvote"
      >
        <svg
          className="w-4 h-4"
          fill="currentColor"
          viewBox="0 0 20 20"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            fillRule="evenodd"
            d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L11 5.414V17a1 1 0 11-2 0V5.414L4.707 9.707a1 1 0 01-1.414 0z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Vote Count */}
      <span
        className={`
        font-semibold min-w-[2rem] text-center
        ${totalVotes > 0 ? 'text-green-400' : totalVotes < 0 ? 'text-red-400' : 'text-gray-400'}
      `}
      >
        {totalVotes > 0 ? '+' : ''}
        {totalVotes}
      </span>

      {/* Downvote Button */}
      <button
        type="button"
        onClick={() => {
          void handleVote('downvote');
        }}
        disabled={isVoting}
        className={`
          ${getButtonSizeClasses()}
          rounded-lg transition-colors duration-200
          ${
            localUserVote === 'downvote'
              ? 'bg-red-600 text-white hover:bg-red-700'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white'
          }
          ${isVoting ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        title="Downvote"
      >
        <svg
          className="w-4 h-4"
          fill="currentColor"
          viewBox="0 0 20 20"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            fillRule="evenodd"
            d="M16.707 10.293a1 1 0 010 1.414l-6 6a1 1 0 01-1.414 0l-6-6a1 1 0 111.414-1.414L9 14.586V3a1 1 0 012 0v11.586l4.293-4.293a1 1 0 011.414 0z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Total Votes */}
      <span className="text-gray-500 text-xs">
        ({localUpvotes + localDownvotes} votes)
      </span>
    </div>
  );
};

export default VoteButtons;
