import React from 'react';
import { Link } from 'react-router-dom';

interface AuthRedirectLinkProps {
  text: string;
  linkText: string;
  to: string;
}

/** The footer line on an auth page pointing at the other auth route. */
const AuthRedirectLink: React.FC<AuthRedirectLinkProps> = ({
  text,
  linkText,
  to,
}) => {
  return (
    <p className="mt-6 text-center text-sm text-gray-400">
      {text}{' '}
      <Link to={to} className="font-medium text-info hover:text-info/90">
        {linkText}
      </Link>
    </p>
  );
};

export default AuthRedirectLink;
