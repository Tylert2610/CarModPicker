import { GiRaceCar, GiCarWheel } from 'react-icons/gi';
import { FaCogs, FaUsers, FaShieldAlt, FaHeart, FaLightbulb, FaRocket } from 'react-icons/fa';
import { BsTools, BsArrowRight } from 'react-icons/bs';
import Button from '../components/common/Button';
import Card from '../components/common/Card';

function About() {
  const features = [
    {
      id: 'build-lists',
      icon: <BsTools className="text-3xl" />,
      title: "Build Lists",
      description: "Create and manage detailed build lists for your car modifications with ease.",
      color: "from-blue-500 to-cyan-500"
    },
    {
      id: 'parts-catalog',
      icon: <FaCogs className="text-3xl" />,
      title: "Parts Catalog",
      description: "Browse thousands of parts from our global catalog shared by the community.",
      color: "from-purple-500 to-pink-500"
    },
    {
      id: 'car-management',
      icon: <GiCarWheel className="text-3xl" />,
      title: "Car Management",
      description: "Keep track of all your vehicles and their modification history.",
      color: "from-green-500 to-emerald-500"
    },
    {
      id: 'community',
      icon: <FaUsers className="text-3xl" />,
      title: "Community",
      description: "Connect with fellow car enthusiasts and share your builds.",
      color: "from-orange-500 to-red-500"
    }
  ];

  const values = [
    {
      id: 'passion',
      icon: <FaHeart className="text-2xl" />,
      title: "Passion",
      description: "We're car enthusiasts just like you, driven by the love of automotive culture.",
      color: "from-red-500 to-pink-500"
    },
    {
      id: 'innovation',
      icon: <FaLightbulb className="text-2xl" />,
      title: "Innovation",
      description: "Constantly evolving our platform with cutting-edge features and technology.",
      color: "from-yellow-500 to-orange-500"
    },
    {
      id: 'quality',
      icon: <FaShieldAlt className="text-2xl" />,
      title: "Quality",
      description: "Ensuring the highest standards for parts and community content.",
      color: "from-green-500 to-emerald-500"
    },
    {
      id: 'community-values',
      icon: <FaUsers className="text-2xl" />,
      title: "Community",
      description: "Building a supportive network of car enthusiasts worldwide.",
      color: "from-blue-500 to-purple-500"
    }
  ];

  const stats = [
    { id: 'active-users', number: "10K+", label: "Active Users", icon: <FaUsers /> },
    { id: 'parts-listed', number: "50K+", label: "Parts Listed", icon: <FaCogs /> },
    { id: 'build-lists-stats', number: "100K+", label: "Build Lists", icon: <BsTools /> }
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-20 px-4 overflow-hidden">
        {/* Enhanced Background Elements */}
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-gradient-to-r from-pink-500/20 to-red-500/20 rounded-full blur-3xl animate-float" style={{ animationDelay: '1s' }}></div>
          <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-gradient-to-r from-green-500/20 to-blue-500/20 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }}></div>
        </div>

        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-5xl mx-auto">
            <div className="animate-fadeInScale">
              {/* Logo */}
              <div className="flex justify-center mb-8">
                <div className="relative">
                  <div className="w-24 h-24 bg-gradient-to-br from-primary-500 via-purple-500 to-pink-500 rounded-3xl flex items-center justify-center shadow-2xl animate-glow">
                    <GiRaceCar className="text-white text-4xl" />
                  </div>
                  <div className="absolute -inset-2 bg-gradient-to-br from-primary-500/30 via-purple-500/30 to-pink-500/30 rounded-3xl blur-xl animate-pulse"></div>
                </div>
              </div>
              
              {/* Title */}
              <h1 className="text-6xl md:text-7xl font-bold mb-8">
                <span className="text-gradient">About CarModPicker</span>
              </h1>
              
              {/* Subtitle */}
              <p className="text-xl md:text-2xl text-neutral-300 mb-8 leading-relaxed">
                Your ultimate platform for discovering, planning, and sharing car modifications
              </p>

              <p className="text-lg text-neutral-400 mb-12 max-w-4xl mx-auto leading-relaxed">
                Whether you're a seasoned car enthusiast looking to customize your ride or just starting your journey, 
                we provide the tools and community to help you build your dream car. Our platform connects passionate 
                car lovers from around the world, creating a space where knowledge, experience, and creativity thrive.
              </p>

              <div className="flex flex-col sm:flex-row gap-6 justify-center">
                <Button size="lg" className="group">
                  <FaRocket className="mr-3 group-hover:translate-x-1 transition-transform" />
                  Join Our Community
                </Button>
                <Button variant="outline" size="lg" className="group">
                  <FaUsers className="mr-3 group-hover:scale-110 transition-transform" />
                  Get in Touch
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Mission Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto">
          <Card variant="glass" className="p-12">
            <div className="text-center">
              <h2 className="text-5xl md:text-6xl font-bold mb-8">
                <span className="text-gradient">Our Mission</span>
              </h2>
              <p className="text-xl text-neutral-400 max-w-4xl mx-auto leading-relaxed">
                To empower car enthusiasts worldwide by providing the most comprehensive platform for discovering, 
                planning, and sharing car modifications. We believe every car has a story, and every enthusiast 
                deserves the tools to tell it.
              </p>
            </div>
          </Card>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-20 animate-slideInUp">
            <h2 className="text-5xl md:text-6xl font-bold mb-8">
              <span className="text-gradient">What We Offer</span>
            </h2>
            <p className="text-xl text-neutral-400 max-w-3xl mx-auto leading-relaxed">
              Powerful tools and features designed specifically for car enthusiasts
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {features.map((feature, index) => (
              <Card 
                key={feature.id}
                variant="glass"
                interactive
                className="group animate-slideInUp"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className="flex items-start space-x-4">
                  <div className={`w-14 h-14 bg-gradient-to-br ${feature.color} rounded-2xl flex items-center justify-center text-white group-hover:scale-110 transition-transform duration-300 shadow-lg`}>
                    {feature.icon}
                  </div>
                  <div className="flex-1">
                    <h3 className="text-xl font-semibold text-white mb-3 group-hover:text-gradient transition-colors">
                      {feature.title}
                    </h3>
                    <p className="text-neutral-400 leading-relaxed">
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
      <section className="py-24 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-20 animate-slideInUp">
            <h2 className="text-5xl md:text-6xl font-bold mb-8">
              <span className="text-gradient">Our Values</span>
            </h2>
            <p className="text-xl text-neutral-400 max-w-3xl mx-auto leading-relaxed">
              The principles that guide everything we do
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {values.map((value, index) => (
              <Card 
                key={value.id}
                variant="glass"
                className="text-center animate-slideInUp"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className={`w-16 h-16 bg-gradient-to-br ${value.color} rounded-2xl flex items-center justify-center text-white mx-auto mb-6 shadow-lg`}>
                  {value.icon}
                </div>
                <h3 className="text-xl font-semibold text-white mb-3 hover:text-gradient transition-colors">
                  {value.title}
                </h3>
                <p className="text-neutral-400 text-sm leading-relaxed">
                  {value.description}
                </p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto">
          <Card variant="glass" className="p-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-12 text-center">
              {stats.map((stat, index) => (
                <div 
                  key={stat.id}
                  className={`animate-slideInUp`}
                  style={{ animationDelay: `${index * 0.2}s` }}
                >
                  <div className="flex justify-center mb-4">
                    <div className="w-16 h-16 bg-gradient-to-br from-primary-500/20 to-purple-500/20 rounded-2xl flex items-center justify-center text-primary-400 text-2xl">
                      {stat.icon}
                    </div>
                  </div>
                  <div className="text-5xl md:text-6xl font-bold text-gradient mb-3">
                    {stat.number}
                  </div>
                  <div className="text-neutral-400 text-lg font-medium">
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto text-center">
          <Card variant="glass" className="max-w-4xl mx-auto p-12">
            <div className="animate-fadeInScale">
              <h2 className="text-5xl md:text-6xl font-bold mb-8">
                <span className="text-gradient">Ready to Start Building?</span>
              </h2>
              <p className="text-xl text-neutral-400 mb-12 max-w-2xl mx-auto leading-relaxed">
                Join thousands of car enthusiasts and start creating amazing modifications today
              </p>
              <div className="flex flex-col sm:flex-row gap-6 justify-center">
                <Button size="lg" className="group">
                  <FaRocket className="mr-3 group-hover:translate-x-1 transition-transform" />
                  Get Started Free
                </Button>
                <Button variant="outline" size="lg" className="group">
                  <BsArrowRight className="mr-3 group-hover:translate-x-1 transition-transform" />
                  Browse Parts
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}

export default About;
