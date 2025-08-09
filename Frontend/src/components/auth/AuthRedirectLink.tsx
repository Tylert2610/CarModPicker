import React from 'react';
import { Link } from 'react-router-dom';

interface AuthRedirectLinkProps {
  text: string;
  linkText: string;
  to: string;
}

const AuthRedirectLink: React.FC<AuthRedirectLinkProps> = ({
  text,
  linkText,
  to,
}) => {
  return (
    <p className="mt-6 text-center text-sm text-gray-400">
      {text}{' '}
      <Link
        to={to}
        className="font-medium text-indigo-400 hover:text-indigo-300"
      >
        {linkText}
      </Link>
    </p>
  );
};

export default AuthRedirectLink;
