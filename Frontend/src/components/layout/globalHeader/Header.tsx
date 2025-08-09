import { Link } from 'react-router-dom';
import { useAuth } from '../../../contexts/AuthContext';
import HeaderNavLink from './HeaderNavLink';
import LoadingSpinner from '../../common/LoadingSpinner';
import HeaderSeparator from './HeaderSeparator';
import { BsTools } from 'react-icons/bs';
import { GrDocumentText } from 'react-icons/gr';
import { GiRaceCar } from 'react-icons/gi';

function Header() {
  const { isAuthenticated, logout, isLoading, user } = useAuth();
  return (
    <header className="bg-gray-950 text-white w-full">
      {/* Top Tier */}
      <div className="container mx-auto flex justify-between items-center p-4">
        <Link to="/" className="text-xl font-bold">
          CarModPicker
        </Link>
        <ul className="flex items-center">
          {' '}
          {isLoading ? (
            <li>
              <LoadingSpinner />
            </li>
          ) : isAuthenticated ? (
            <>
              <li>
                <HeaderNavLink to="/profile">
                  Profile ({user?.username})
                </HeaderNavLink>
              </li>
              <HeaderSeparator />
              <li>
                <button
                  onClick={logout}
                  className="text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 text-sm font-medium bg-transparent border-none"
                >
                  Logout
                </button>
              </li>
            </>
          ) : (
            <>
              <li>
                <HeaderNavLink to="/login">Login</HeaderNavLink>
              </li>
              <HeaderSeparator />
              <li>
                <HeaderNavLink to="/register">Register</HeaderNavLink>
              </li>
            </>
          )}
        </ul>
      </div>

      {/* Bottom Tier - Navigation */}
      <nav className="bg-gray-950 border-t border-b border-gray-500 w-full">
        <div className="container mx-auto flex">
          <ul className="flex">
            <HeaderSeparator />
            <li>
              <HeaderNavLink to="/builder" icon={<BsTools />}>
                Builder
              </HeaderNavLink>
            </li>
            <HeaderSeparator />
            <li>
              <HeaderNavLink to="/guides" icon={<GrDocumentText />}>
                Guides
              </HeaderNavLink>
            </li>
            <HeaderSeparator />
            <li>
              <HeaderNavLink to="/builder/my-buildlists" icon={<GiRaceCar />}>
                My Builds
              </HeaderNavLink>
            </li>
            <HeaderSeparator />
          </ul>
        </div>
      </nav>
    </header>
  );
}

export default Header;
