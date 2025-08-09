function Footer() {
  return (
    <footer className="bg-gray-950 text-white p-4 mt-auto w-full text-center">
      <div className="container mx-auto">
        <p>
          &copy; {new Date().getFullYear()} CarModPicker. All rights reserved.
        </p>
        <div className="flex justify-center space-x-4 mt-2">
          <a href="/about" className="hover:text-gray-300">
            About Us
          </a>
          <a href="/contact-us" className="hover:text-gray-300">
            Contact
          </a>
          <a href="/privacy-policy" className="hover:text-gray-300">
            Privacy Policy
          </a>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
