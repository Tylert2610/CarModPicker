import { Link } from 'react-router-dom';
import { GiRaceCar } from 'react-icons/gi';
import { FaGithub, FaTwitter, FaLinkedin } from 'react-icons/fa';

function Footer() {
  return (
    <footer className="relative mt-auto w-full">
      {/* Background with gradient */}
      <div className="absolute inset-0 bg-gradient-to-r from-neutral-900 via-neutral-800 to-neutral-900 opacity-95"></div>
      
      {/* Footer Content */}
      <div className="relative">
        {/* Main Footer */}
        <div className="container mx-auto px-4 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {/* Brand Section */}
            <div className="col-span-1 md:col-span-2">
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center">
                  <GiRaceCar className="text-white text-sm" />
                </div>
                <span className="text-xl font-bold bg-gradient-to-r from-white to-neutral-300 bg-clip-text text-transparent">
                  CarModPicker
                </span>
              </div>
              <p className="text-neutral-400 text-sm leading-relaxed max-w-md">
                Your ultimate platform for discovering, planning, and sharing car modifications. 
                Build, customize, and connect with fellow car enthusiasts.
              </p>
            </div>

            {/* Quick Links */}
            <div>
              <h3 className="text-white font-semibold mb-4 text-sm uppercase tracking-wider">
                Quick Links
              </h3>
              <ul className="space-y-2">
                <li>
                  <Link 
                    to="/about" 
                    className="text-neutral-400 hover:text-white transition-colors duration-300 text-sm"
                  >
                    About Us
                  </Link>
                </li>
                <li>
                  <Link 
                    to="/contact-us" 
                    className="text-neutral-400 hover:text-white transition-colors duration-300 text-sm"
                  >
                    Contact
                  </Link>
                </li>
                <li>
                  <Link 
                    to="/privacy-policy" 
                    className="text-neutral-400 hover:text-white transition-colors duration-300 text-sm"
                  >
                    Privacy Policy
                  </Link>
                </li>
                <li>
                  <Link 
                    to="/global-parts" 
                    className="text-neutral-400 hover:text-white transition-colors duration-300 text-sm"
                  >
                    Parts Catalog
                  </Link>
                </li>
              </ul>
            </div>

            {/* Social Links */}
            <div>
              <h3 className="text-white font-semibold mb-4 text-sm uppercase tracking-wider">
                Connect
              </h3>
              <div className="flex space-x-4">
                <a 
                  href="https://github.com" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="w-10 h-10 glass rounded-lg flex items-center justify-center text-neutral-400 hover:text-white hover:bg-white/10 transition-all duration-300"
                >
                  <FaGithub className="text-lg" />
                </a>
                <a 
                  href="https://twitter.com" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="w-10 h-10 glass rounded-lg flex items-center justify-center text-neutral-400 hover:text-white hover:bg-white/10 transition-all duration-300"
                >
                  <FaTwitter className="text-lg" />
                </a>
                <a 
                  href="https://linkedin.com" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="w-10 h-10 glass rounded-lg flex items-center justify-center text-neutral-400 hover:text-white hover:bg-white/10 transition-all duration-300"
                >
                  <FaLinkedin className="text-lg" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-white/10">
          <div className="container mx-auto px-4 py-6">
            <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
              <p className="text-neutral-400 text-sm">
                &copy; {new Date().getFullYear()} CarModPicker. All rights reserved.
              </p>
              <div className="flex items-center space-x-6 text-sm">
                <span className="text-neutral-500">Made with ❤️ for car enthusiasts</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
