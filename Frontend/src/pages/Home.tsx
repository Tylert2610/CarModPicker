import { useAuth } from '../contexts/AuthContext';
import LinkButton from '../components/buttons/LinkButton';

export default function HomePage() {
  const { user, isAuthenticated } = useAuth();

  return (
    <div className="container mx-auto p-4 text-center">
      <h1 className="text-4xl font-bold mb-6">Welcome to CarModPicker!</h1>
      {isAuthenticated && user ? (
        <>
          <p className="text-2xl mb-4">Hello, {user.username}!</p>
          <p className="text-lg">
            Explore and manage your car modifications with ease.
          </p>
          <div className="mt-8">
            <LinkButton to="/builder">Start Your Build</LinkButton>
          </div>
        </>
      ) : (
        <>
          <p className="text-xl mb-4">
            Your ultimate platform for discovering, planning, and sharing car
            modifications.
          </p>
          <div className="mt-8">
            <LinkButton to="/login">Login to Start Your Build</LinkButton>
          </div>
          <p className="text-lg mt-6">
            Please{' '}
            <a href="/login" className="text-indigo-400 hover:text-indigo-300">
              Login
            </a>{' '}
            or{' '}
            <a
              href="/register"
              className="text-indigo-400 hover:text-indigo-300"
            >
              Register
            </a>{' '}
            to get started.
          </p>
        </>
      )}
    </div>
  );
}
