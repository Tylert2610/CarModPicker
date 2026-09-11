import React from 'react';

interface AuthFormProps {
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  children: React.ReactNode;
}

/** The form element shared by the auth pages. */
const AuthForm: React.FC<AuthFormProps> = ({ onSubmit, children }) => {
  return (
    <form className="mt-8 space-y-6" onSubmit={onSubmit}>
      {children}
    </form>
  );
};

export default AuthForm;
