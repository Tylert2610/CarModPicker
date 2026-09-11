import { FaCoffee, FaCrown, FaHeart } from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import { useIsPremiumSystemDisabled } from '../hooks/useIsPremium';

type SupportOption = {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  link: string;
  buttonText: string;
  external: boolean;
};

/** Static support page pointing at help resources and contact routes. */
function Support() {
  const premiumSystemDisabled = useIsPremiumSystemDisabled();
  useDocumentMeta({
    title: 'Support CarModPicker',
    description: premiumSystemDisabled
      ? 'Ways to support CarModPicker: send feedback or help grow the community.'
      : 'Ways to support CarModPicker: subscribe to Premium, send feedback, or help grow the community.',
    canonicalPath: '/support',
  });
  const supportOptions: SupportOption[] = [
    ...(premiumSystemDisabled
      ? []
      : [
          {
            id: 'premium',
            title: 'Subscribe to Premium',
            description:
              'Go ad-free, unlock unlimited build lists, and support ongoing development with a monthly subscription.',
            icon: <FaCrown className="text-3xl" />,
            color: 'from-warning to-warning',
            link: '/pricing',
            buttonText: 'See Pricing',
            external: false,
          } satisfies SupportOption,
        ]),
    {
      id: 'coffee',
      title: 'Buy Me a Coffee',
      description:
        'Prefer a one-time donation? Every contribution helps keep CarModPicker running!',
      icon: <FaCoffee className="text-3xl" />,
      color: 'from-warning to-warning',
      link: 'https://buymeacoffee.com/webbpulse', // Replace with actual link
      buttonText: 'Buy Me a Coffee',
      external: true,
    },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-10 px-4">
        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-5xl mx-auto">
            <div className="animate-fadeInScale">
              {/* Icon */}
              <div className="flex justify-center mb-4">
                <div className="relative">
                  <div className="w-20 h-20 bg-linear-to-br from-warning to-warning rounded-3xl flex items-center justify-center shadow-2xl animate-glow">
                    <FaCoffee className="text-white text-3xl" />
                  </div>
                  <div className="absolute -inset-2 bg-warning/30 rounded-3xl blur-xl animate-pulse"></div>
                </div>
              </div>

              {/* Title */}
              <h1 className="text-5xl md:text-6xl font-bold mb-4">
                <span className="text-gradient">Support CarModPicker</span>
              </h1>

              {/* Subtitle */}
              <p className="text-xl md:text-2xl text-foreground mb-3 leading-relaxed">
                Help us keep the platform running and improving
              </p>

              <p className="text-lg text-muted-foreground mb-6 max-w-4xl mx-auto leading-relaxed">
                CarModPicker is built with passion and dedication to serve the
                car enthusiast community. Your support helps us maintain
                servers, develop new features, and keep the platform free for
                everyone. Every contribution, no matter how small, makes a
                difference!
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Support Options Section */}
      <section className="py-8 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-8 animate-slideInUp">
            <h2 className="text-4xl md:text-5xl font-bold mb-4">
              <span className="text-gradient">Ways to Support</span>
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
              Choose the method that works best for you
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {supportOptions.map((option, index) => (
              <Card
                key={option.id}
                variant="glass"
                className="group animate-slideInUp text-center flex flex-col cursor-pointer transition-transform hover:scale-105"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div
                  className={`w-14 h-14 bg-linear-to-br ${option.color} rounded-2xl flex items-center justify-center text-white mx-auto mb-4 group-hover:scale-110 transition-transform duration-300 shadow-lg`}
                >
                  {option.icon}
                </div>
                <h3 className="text-2xl font-semibold text-white mb-3 group-hover:text-gradient transition-colors">
                  {option.title}
                </h3>
                <p className="text-muted-foreground mb-4 leading-relaxed flex-grow">
                  {option.description}
                </p>
                {option.external ? (
                  <a
                    href={option.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block"
                  >
                    <Button className="w-full bg-primary hover:bg-primary/90 text-white">
                      {option.buttonText}
                    </Button>
                  </a>
                ) : (
                  <Link to={option.link} className="block">
                    <Button className="w-full bg-primary hover:bg-primary/90 text-white">
                      {option.buttonText}
                    </Button>
                  </Link>
                )}
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Why Support Section */}
      <section className="py-8 px-4">
        <div className="container mx-auto">
          <Card variant="glass" className="p-8 max-w-4xl mx-auto">
            <div className="text-center">
              <div className="flex justify-center mb-4">
                <FaHeart className="text-4xl text-red-500 animate-pulse" />
              </div>
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                <span className="text-gradient">Why Your Support Matters</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 text-left">
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary" />
                    Keep It Free
                  </h3>
                  <p className="text-muted-foreground leading-relaxed">
                    Your donations help us keep CarModPicker free and accessible
                    to all car enthusiasts, without requiring subscriptions or
                    paywalls for core features.
                  </p>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary" />
                    Better Features
                  </h3>
                  <p className="text-muted-foreground leading-relaxed">
                    Support enables us to develop new features, improve
                    performance, and enhance the overall user experience for the
                    entire community.
                  </p>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary" />
                    Reliable Service
                  </h3>
                  <p className="text-muted-foreground leading-relaxed">
                    Contributions help maintain servers, ensure uptime, and
                    provide reliable access to your build lists and parts
                    catalog.
                  </p>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary" />
                    Community Growth
                  </h3>
                  <p className="text-muted-foreground leading-relaxed">
                    Your support helps us grow the community, add more cars and
                    parts, and create a better platform for car enthusiasts
                    worldwide.
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Thank You Section */}
      <section className="py-8 px-4 pb-10">
        <div className="container mx-auto">
          <div className="text-center max-w-3xl mx-auto">
            <div className="animate-fadeInScale">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                <span className="text-gradient">Thank You!</span>
              </h2>
              <p className="text-xl text-foreground leading-relaxed">
                Whether you choose to support us financially or by being an
                active member of our community, we appreciate you being part of
                CarModPicker. Together, we're building something amazing for car
                enthusiasts everywhere.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Support;
