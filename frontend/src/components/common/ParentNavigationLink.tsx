import React from 'react';
import { Link } from 'react-router-dom';

interface ParentNavigationLinkProps {
  label?: string;
  linkTo: string;
  linkText: string;
  show?: boolean;
}

const ParentNavigationLink: React.FC<ParentNavigationLinkProps> = ({
  label,
  linkTo,
  linkText,
  show = true, // Default to true, so it shows unless 'show' is explicitly false
}) => {
  if (!show) {
    return null;
  }

  return (
    <p>
      <strong>{label}</strong>
      <Link
        to={linkTo}
        className="text-indigo-400 hover:text-indigo-300 underline"
      >
        {linkText}
      </Link>
    </p>
  );
};

export default ParentNavigationLink;
