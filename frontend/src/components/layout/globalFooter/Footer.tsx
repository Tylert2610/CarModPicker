import { FaGithub, FaLinkedin, FaTwitter } from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import { Link } from 'react-router-dom';

import { useCookieConsent } from '../../../hooks/useCookieConsent';

/** The site footer: quick links, social links, and the copyright bar. */
function Footer() {
  const { reset: resetCookieConsent } = useCookieConsent();

  return (
    <footer className="relative mt-auto w-full">
      <div className="absolute inset-0 bg-linear-to-r from-card via-muted to-card opacity-95"></div>

      <div className="relative">
        <div className="container mx-auto px-4 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="col-span-1 md:col-span-2">
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-linear-to-br from-primary to-primary rounded-lg flex items-center justify-center">
                  <GiRaceCar className="text-white text-sm" />
                </div>
                <span className="text-xl font-bold bg-linear-to-r from-white to-foreground bg-clip-text text-transparent">
                  CarModPicker
                </span>
              </div>
              <p className="text-muted-foreground text-sm leading-relaxed max-w-md">
                Your ultimate platform for discovering, planning, and sharing
                car modifications. Build, customize, and connect with fellow car
                enthusiasts.
              </p>
            </div>

            <div>
              <h3 className="text-white font-semibold mb-4 text-sm uppercase tracking-wider">
                Quick Links
              </h3>
              <ul className="space-y-2">
                <li>
                  <Link
                    to="/about"
                    className="text-muted-foreground hover:text-white transition-colors duration-300 text-sm"
                  >
                    About Us
                  </Link>
                </li>
                <li>
                  <Link
                    to="/contact-us"
                    className="text-muted-foreground hover:text-white transition-colors duration-300 text-sm"
                  >
                    Contact
                  </Link>
                </li>
                <li>
                  <Link
                    to="/privacy-policy"
                    className="text-muted-foreground hover:text-white transition-colors duration-300 text-sm"
                  >
                    Privacy Policy
                  </Link>
                </li>
                <li>
                  <Link
                    to="/terms-of-service"
                    className="text-muted-foreground hover:text-white transition-colors duration-300 text-sm"
                  >
                    Terms of Service
                  </Link>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={resetCookieConsent}
                    className="text-muted-foreground hover:text-white transition-colors duration-300 text-sm text-left"
                  >
                    Cookie preferences
                  </button>
                </li>
                <li>
                  <Link
                    to="/bug-report"
                    className="text-muted-foreground hover:text-white transition-colors duration-300 text-sm"
                  >
                    Report a Bug
                  </Link>
                </li>
                <li>
                  <Link
                    to="/support"
                    className="text-muted-foreground hover:text-white transition-colors duration-300 text-sm"
                  >
                    Support Us
                  </Link>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-white font-semibold mb-4 text-sm uppercase tracking-wider">
                Connect
              </h3>
              <div className="flex space-x-4">
                <a
                  href="https://github.com/TW-WebbPulse"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 border border-white/10 bg-white/5 backdrop-blur-md rounded-lg flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/10 transition-all duration-300"
                >
                  <FaGithub className="text-lg" />
                </a>
                <a
                  href="https://twitter.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 border border-white/10 bg-white/5 backdrop-blur-md rounded-lg flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/10 transition-all duration-300"
                >
                  <FaTwitter className="text-lg" />
                </a>
                <a
                  href="https://www.linkedin.com/in/tylert2610/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 border border-white/10 bg-white/5 backdrop-blur-md rounded-lg flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/10 transition-all duration-300"
                >
                  <FaLinkedin className="text-lg" />
                </a>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-white/10">
          <div className="container mx-auto px-4 py-6">
            <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
              <p className="text-muted-foreground text-sm">
                &copy; {new Date().getFullYear()} CarModPicker. All rights
                reserved.
              </p>
              <div className="flex items-center space-x-6 text-sm">
                <span className="text-muted-foreground">
                  Made with ❤️ for car enthusiasts
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
