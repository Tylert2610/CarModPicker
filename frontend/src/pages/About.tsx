import { BsTools } from 'react-icons/bs';
import {
  FaHeart,
  FaLightbulb,
  FaRocket,
  FaShieldAlt,
  FaUsers,
} from 'react-icons/fa';
import { GiCarWheel, GiRaceCar } from 'react-icons/gi';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { useDocumentMeta } from '../hooks/useDocumentMeta';

/** Static marketing page describing the product and the team behind it. */
function About() {
  useDocumentMeta({
    title: 'About',
    description:
      'Learn about CarModPicker — a platform where car enthusiasts plan modifications, track build progress, and share their work with the community.',
    canonicalPath: '/about',
  });
  const features = [
    {
      id: 'build-lists',
      icon: <BsTools className="text-3xl" />,
      title: 'Build Lists',
      description:
        'Create and manage detailed build lists for your car modifications with ease.',
      color: 'from-blue-500 to-cyan-500',
    },
    {
      id: 'car-management',
      icon: <GiCarWheel className="text-3xl" />,
      title: 'Car Management',
      description:
        'Keep track of all your vehicles and their modification history.',
      color: 'from-green-500 to-success',
    },
    {
      id: 'community',
      icon: <FaUsers className="text-3xl" />,
      title: 'Community',
      description: 'Connect with fellow car enthusiasts and share your builds.',
      color: 'from-orange-500 to-red-500',
    },
  ];

  const values = [
    {
      id: 'passion',
      icon: <FaHeart className="text-2xl" />,
      title: 'Passion',
      description:
        "We're car enthusiasts just like you, driven by the love of automotive culture.",
      color: 'from-red-500 to-pink-500',
    },
    {
      id: 'innovation',
      icon: <FaLightbulb className="text-2xl" />,
      title: 'Innovation',
      description:
        'Constantly evolving our platform with cutting-edge features and technology.',
      color: 'from-yellow-500 to-orange-500',
    },
    {
      id: 'quality',
      icon: <FaShieldAlt className="text-2xl" />,
      title: 'Quality',
      description:
        'Ensuring the highest standards for parts and community content.',
      color: 'from-green-500 to-success',
    },
    {
      id: 'community-values',
      icon: <FaUsers className="text-2xl" />,
      title: 'Community',
      description:
        'Building a supportive network of car enthusiasts worldwide.',
      color: 'from-blue-500 to-purple-500',
    },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-10 px-4">
        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-5xl mx-auto">
            <div className="animate-fadeInScale">
              {/* Logo */}
              <div className="flex justify-center mb-4">
                <div className="relative">
                  <div className="w-20 h-20 bg-linear-to-br from-primary via-purple-500 to-pink-500 rounded-3xl flex items-center justify-center shadow-2xl animate-glow">
                    <GiRaceCar className="text-white text-3xl" />
                  </div>
                  <div className="absolute -inset-2 bg-linear-to-br from-primary/30 via-purple-500/30 to-pink-500/30 rounded-3xl blur-xl animate-pulse"></div>
                </div>
              </div>

              {/* Title */}
              <h1 className="text-5xl md:text-6xl font-bold mb-4">
                <span className="text-gradient">About CarModPicker</span>
              </h1>

              {/* Subtitle */}
              <p className="text-xl md:text-2xl text-foreground mb-3 leading-relaxed">
                Your ultimate platform for discovering, planning, and sharing
                car modifications
              </p>

              <p className="text-lg text-muted-foreground mb-6 max-w-4xl mx-auto leading-relaxed">
                Whether you're a seasoned car enthusiast looking to customize
                your ride or just starting your journey, we provide the tools
                and community to help you build your dream car. Our platform
                connects passionate car lovers from around the world, creating a
                space where knowledge, experience, and creativity thrive.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button size="lg" className="group">
                  <FaRocket className="group-hover:translate-x-1 transition-transform" />
                  Join Our Community
                </Button>
                <Button variant="outline" size="lg" className="group">
                  <FaUsers className="group-hover:scale-110 transition-transform" />
                  Get in Touch
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Mission Section */}
      <section className="py-8 px-4">
        <div className="container mx-auto">
          <Card variant="glass" className="p-8">
            <div className="text-center">
              <h2 className="text-4xl md:text-5xl font-bold mb-4">
                <span className="text-gradient">Our Mission</span>
              </h2>
              <p className="text-xl text-muted-foreground max-w-4xl mx-auto leading-relaxed">
                To empower car enthusiasts worldwide by providing the most
                comprehensive platform for discovering, planning, and sharing
                car modifications. We believe every car has a story, and every
                enthusiast deserves the tools to tell it.
              </p>
            </div>
          </Card>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-8 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-8 animate-slideInUp">
            <h2 className="text-4xl md:text-5xl font-bold mb-4">
              <span className="text-gradient">What We Offer</span>
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
              Powerful tools and features designed specifically for car
              enthusiasts
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {features.map((feature, index) => (
              <Card
                key={feature.id}
                variant="glass"
                className="group animate-slideInUp cursor-pointer transition-transform hover:scale-105"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className="flex items-start space-x-4">
                  <div
                    className={`w-12 h-12 bg-linear-to-br ${feature.color} rounded-2xl flex items-center justify-center text-white group-hover:scale-110 transition-transform duration-300 shadow-lg shrink-0`}
                  >
                    {feature.icon}
                  </div>
                  <div className="flex-1">
                    <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-gradient transition-colors">
                      {feature.title}
                    </h3>
                    <p className="text-muted-foreground leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Values Section */}
      <section className="py-8 px-4 pb-10">
        <div className="container mx-auto">
          <div className="text-center mb-8 animate-slideInUp">
            <h2 className="text-4xl md:text-5xl font-bold mb-4">
              <span className="text-gradient">Our Values</span>
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
              The principles that guide everything we do
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {values.map((value, index) => (
              <Card
                key={value.id}
                variant="glass"
                className="text-center animate-slideInUp"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div
                  className={`w-14 h-14 bg-linear-to-br ${value.color} rounded-2xl flex items-center justify-center text-white mx-auto mb-4 shadow-lg`}
                >
                  {value.icon}
                </div>
                <h3 className="text-xl font-semibold text-white mb-2 hover:text-gradient transition-colors">
                  {value.title}
                </h3>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  {value.description}
                </p>
              </Card>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

export default About;
