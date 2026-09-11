import { Card } from '../components/ui/card';
import { useDocumentMeta } from '../hooks/useDocumentMeta';

/** Static contact page listing the business, support, and DMCA addresses. */
function ContactUs() {
  useDocumentMeta({
    title: 'Contact Us',
    description:
      'Get in touch with the CarModPicker team. Send feedback, questions, or business inquiries — we read every message.',
    canonicalPath: '/contact-us',
  });
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-10 px-4">
        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-5xl mx-auto">
            <div className="animate-fadeInScale">
              <h1 className="text-6xl md:text-7xl font-bold mb-4">
                <span className="text-gradient">Contact Us</span>
              </h1>
              <p className="text-xl md:text-2xl text-foreground mb-4 leading-relaxed">
                We'd love to hear from you
              </p>
              <p className="text-lg text-muted-foreground mb-6 max-w-4xl mx-auto leading-relaxed">
                Have questions, feedback, or want to get in touch? We're here to
                help and always happy to connect with our community.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Business Inquiries Section */}
      <section className="py-8 px-4">
        <div className="container mx-auto text-center">
          <Card variant="glass" className="max-w-4xl mx-auto p-8">
            <div className="animate-fadeInScale">
              <h2 className="text-5xl md:text-6xl font-bold mb-4">
                <span className="text-gradient">Business Inquiries</span>
              </h2>
              <p className="text-xl text-muted-foreground mb-4 max-w-2xl mx-auto leading-relaxed">
                Interested in partnering with us or have a business proposal?
                We'd love to hear from you.
              </p>
              <p className="text-lg text-foreground mb-3">
                Please send all business inquiries to:
              </p>
              <a
                href="mailto:tyler@webbpulse.com"
                className="text-2xl font-semibold text-gradient hover:underline inline-block"
              >
                tyler@webbpulse.com
              </a>
            </div>
          </Card>
        </div>
      </section>

      {/* Tech Support Section */}
      <section className="py-8 px-4">
        <div className="container mx-auto text-center">
          <Card variant="glass" className="max-w-4xl mx-auto p-8">
            <div className="animate-fadeInScale">
              <h2 className="text-5xl md:text-6xl font-bold mb-4">
                <span className="text-gradient">Tech Support</span>
              </h2>
              <p className="text-xl text-muted-foreground mb-4 max-w-2xl mx-auto leading-relaxed">
                Running into a bug or need help with the site? Reach out and
                we'll get you sorted.
              </p>
              <p className="text-lg text-foreground mb-3">
                For tech support, email:
              </p>
              <a
                href="mailto:tyler@webbpulse.com"
                className="text-2xl font-semibold text-gradient hover:underline inline-block"
              >
                tyler@webbpulse.com
              </a>
            </div>
          </Card>
        </div>
      </section>

      {/* DMCA / Copyright Section */}
      <section className="py-8 px-4">
        <div className="container mx-auto text-center">
          <Card variant="glass" className="max-w-4xl mx-auto p-8">
            <div className="animate-fadeInScale">
              <h2 className="text-5xl md:text-6xl font-bold mb-4">
                <span className="text-gradient">DMCA & Copyright</span>
              </h2>
              <p className="text-xl text-muted-foreground mb-4 max-w-2xl mx-auto leading-relaxed">
                If you believe that material on CarModPicker violates your
                copyright, please notify us in accordance with our DMCA policy.
                We will respond to valid notices and address infringing content
                as required by law.
              </p>
              <p className="text-lg text-foreground mb-3">DMCA complaints:</p>
              <a
                href="mailto:tyler@webbpulse.com"
                className="text-2xl font-semibold text-gradient hover:underline inline-block"
              >
                tyler@webbpulse.com
              </a>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}

export default ContactUs;
