import { Link } from 'react-router-dom';
import { useAuth } from '../../../hooks/useAuth';
import LoadingSpinner from '../../common/LoadingSpinner';
import { BsTools, BsGear } from 'react-icons/bs';
import { GrDocumentText } from 'react-icons/gr';
import { GiRaceCar } from 'react-icons/gi';
import { FaCogs, FaUser, FaSignOutAlt, FaBars, FaTimes } from 'react-icons/fa';
import { useState } from 'react';

function Header() {
  const { isAuthenticated, logout, isLoading, user } = useAuth();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const handleLogout = () => {
    void logout();
    setIsMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 w-full">
      {/* Background with gradient */}
      <div className="absolute inset-0 bg-gradient-to-r from-neutral-900 via-neutral-800 to-neutral-900 opacity-95 backdrop-blur-md"></div>
      
      {/* Main Header Content */}
      <div className="relative">
        {/* Top Tier - Logo and Auth */}
        <div className="container mx-auto px-4 py-3">
          <div className="flex justify-between items-center">
            {/* Logo */}
            <Link 
              to="/" 
              className="flex items-center space-x-2 group animate-slideInLeft"
            >
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center shadow-lg group-hover:shadow-primary-500/25 transition-all duration-300 group-hover:scale-110">
                <GiRaceCar className="text-white text-xl" />
              </div>
              <span className="text-2xl font-bold bg-gradient-to-r from-white to-neutral-300 bg-clip-text text-transparent">
                CarModPicker
              </span>
            </Link>

            {/* Desktop Auth Section */}
            <div className="hidden md:flex items-center space-x-4">
              {isLoading ? (
                <div className="flex items-center space-x-2">
                  <LoadingSpinner />
                  <span className="text-sm text-neutral-400">Loading...</span>
                </div>
              ) : isAuthenticated ? (
                <div className="flex items-center space-x-4">
                  <Link
                    to="/profile"
                    className="flex items-center space-x-2 glass px-4 py-2 rounded-xl hover:bg-white/10 transition-all duration-300 group"
                  >
                    <FaUser className="text-primary-400 group-hover:scale-110 transition-transform duration-300" />
                    <span className="text-sm font-medium text-white">
                      {user?.username}
                    </span>
                  </Link>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex items-center space-x-2 glass-button px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary-300 transition-all duration-300"
                  >
                    <FaSignOutAlt />
                    <span>Logout</span>
                  </button>
                </div>
              ) : (
                <div className="flex items-center space-x-3">
                  <Link
                    to="/login"
                    className="glass-button px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary-300 transition-all duration-300"
                  >
                    Login
                  </Link>
                  <Link
                    to="/register"
                    className="btn-primary px-4 py-2 rounded-xl text-sm font-medium"
                  >
                    Register
                  </Link>
                </div>
              )}

              {/* Mobile Menu Button */}
              <button
                type="button"
                onClick={toggleMobileMenu}
                className="md:hidden glass-button p-2 rounded-lg text-white hover:text-primary-300 transition-all duration-300"
              >
                {isMobileMenuOpen ? <FaTimes /> : <FaBars />}
              </button>
            </div>
          </div>
        </div>

        {/* Bottom Tier - Navigation */}
        <nav className="border-t border-white/10">
          <div className="container mx-auto px-4">
            <div className="hidden md:flex items-center space-x-1 py-2">
              <NavLink to="/builder" icon={<BsTools />}>
                Builder
              </NavLink>
              <NavLink to="/global-parts" icon={<FaCogs />}>
                Parts Catalog
              </NavLink>
              <NavLink to="/my-global-parts" icon={<BsGear />}>
                My Parts
              </NavLink>
              <NavLink to="/guides" icon={<GrDocumentText />}>
                Guides
              </NavLink>
              <NavLink to="/builder/my-buildlists" icon={<GiRaceCar />}>
                My Builds
              </NavLink>
              {user?.is_admin && (
                <NavLink to="/admin" icon={<FaCogs />}>
                  Admin
                </NavLink>
              )}
            </div>
          </div>
        </nav>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden animate-slideInUp">
            <div className="glass-card mx-4 mb-4 rounded-xl border border-white/10">
              <div className="p-4 space-y-3">
                {isAuthenticated ? (
                  <div className="space-y-3">
                    <Link
                      to="/profile"
                      className="flex items-center space-x-2 text-white hover:text-primary-300 transition-colors duration-300"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      <FaUser className="text-primary-400" />
                      <span className="font-medium">{user?.username}</span>
                    </Link>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="w-full flex items-center justify-center space-x-2 glass-button px-4 py-2 rounded-xl text-sm font-medium text-white"
                    >
                      <FaSignOutAlt />
                      <span>Logout</span>
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <Link
                      to="/login"
                      className="block w-full text-center glass-button px-4 py-2 rounded-xl text-sm font-medium text-white"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      Login
                    </Link>
                    <Link
                      to="/register"
                      className="block w-full text-center btn-primary px-4 py-2 rounded-xl text-sm font-medium"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      Register
                    </Link>
                  </div>
                )}
                
                <div className="border-t border-white/10 pt-3 space-y-2">
                  <MobileNavLink to="/builder" icon={<BsTools />} onClick={() => setIsMobileMenuOpen(false)}>
                    Builder
                  </MobileNavLink>
                  <MobileNavLink to="/global-parts" icon={<FaCogs />} onClick={() => setIsMobileMenuOpen(false)}>
                    Parts Catalog
                  </MobileNavLink>
                  <MobileNavLink to="/my-global-parts" icon={<BsGear />} onClick={() => setIsMobileMenuOpen(false)}>
                    My Parts
                  </MobileNavLink>
                  <MobileNavLink to="/guides" icon={<GrDocumentText />} onClick={() => setIsMobileMenuOpen(false)}>
                    Guides
                  </MobileNavLink>
                  <MobileNavLink to="/builder/my-buildlists" icon={<GiRaceCar />} onClick={() => setIsMobileMenuOpen(false)}>
                    My Builds
                  </MobileNavLink>
                  {user?.is_admin && (
                    <MobileNavLink to="/admin" icon={<FaCogs />} onClick={() => setIsMobileMenuOpen(false)}>
                      Admin
                    </MobileNavLink>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}

// Desktop Navigation Link Component
function NavLink({ to, icon, children }: { to: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="flex items-center space-x-2 px-4 py-3 text-sm font-medium text-neutral-300 hover:text-white hover:bg-white/5 rounded-xl transition-all duration-300 group"
    >
      <span className="group-hover:scale-110 transition-transform duration-300">
        {icon}
      </span>
      <span>{children}</span>
    </Link>
  );
}

// Mobile Navigation Link Component
function MobileNavLink({ 
  to, 
  icon, 
  children, 
  onClick 
}: { 
  to: string; 
  icon: React.ReactNode; 
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="flex items-center space-x-3 px-3 py-2 text-sm font-medium text-neutral-300 hover:text-white hover:bg-white/5 rounded-lg transition-all duration-300"
    >
      <span className="text-lg">{icon}</span>
      <span>{children}</span>
    </Link>
  );
}

export default Header;
