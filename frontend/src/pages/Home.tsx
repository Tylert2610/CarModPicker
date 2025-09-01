import { useAuth } from '../hooks/useAuth';
import LinkButton from '../components/buttons/LinkButton';
import { GiRaceCar, GiCarWheel } from 'react-icons/gi';
import { FaCogs, FaUsers, FaChartLine, FaShieldAlt } from 'react-icons/fa';
import { BsTools } from 'react-icons/bs';

export default function HomePage() {
  const { user, isAuthenticated } = useAuth();

  const features = [
    {
      id: 'build-lists-home',
      icon: <BsTools className="text-3xl" />,
      title: "Build Lists",
      description: "Create and manage detailed build lists for your car modifications with ease."
    },
    {
      id: 'parts-catalog-home',
      icon: <FaCogs className="text-3xl" />,
      title: "Parts Catalog",
      description: "Browse thousands of parts from our global catalog shared by the community."
    },
    {
      id: 'car-management-home',
      icon: <GiCarWheel className="text-3xl" />,
      title: "Car Management",
      description: "Keep track of all your vehicles and their modification history."
    },
    {
      id: 'community-home',
      icon: <FaUsers className="text-3xl" />,
      title: "Community",
      description: "Connect with fellow car enthusiasts and share your builds."
    },
    {
      id: 'analytics',
      icon: <FaChartLine className="text-3xl" />,
      title: "Analytics",
      description: "Track your build progress and see detailed statistics."
    },
    {
      id: 'verified-parts',
      icon: <FaShieldAlt className="text-3xl" />,
      title: "Verified Parts",
      description: "Quality assurance with community-verified part listings."
    }
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-20 px-4">
        {/* Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl animate-float"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-primary-400/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '1s' }}></div>
        </div>

        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-4xl mx-auto">
            <div className="animate-slideInUp">
              <div className="flex justify-center mb-6">
                <div className="w-20 h-20 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center shadow-2xl animate-glow">
                  <GiRaceCar className="text-white text-3xl" />
                </div>
              </div>
              
              <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-primary-100 to-primary-300 bg-clip-text text-transparent">
                CarModPicker
              </h1>
              
              <p className="text-xl md:text-2xl text-neutral-300 mb-8 leading-relaxed">
                Your ultimate platform for discovering, planning, and sharing car modifications
              </p>

              {isAuthenticated && user ? (
                <div className="space-y-6">
                  <p className="text-lg text-neutral-400">
                    Welcome back, <span className="text-primary-400 font-semibold">{user.username}</span>!
                  </p>
                  <div className="flex flex-col sm:flex-row gap-4 justify-center">
                    <LinkButton to="/builder" size="lg">
                      <BsTools className="mr-2" />
                      Start Your Build
                    </LinkButton>
                    <LinkButton to="/global-parts" variant="secondary" size="lg">
                      <FaCogs className="mr-2" />
                      Browse Parts
                    </LinkButton>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="flex flex-col sm:flex-row gap-4 justify-center">
                    <LinkButton to="/register" size="lg">
                      <GiRaceCar className="mr-2" />
                      Get Started Free
                    </LinkButton>
                    <LinkButton to="/login" variant="secondary" size="lg">
                      <FaUsers className="mr-2" />
                      Sign In
                    </LinkButton>
                  </div>
                  <p className="text-sm text-neutral-500">
                    Join thousands of car enthusiasts worldwide
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-16 animate-slideInUp">
            <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-white to-neutral-300 bg-clip-text text-transparent">
              Everything You Need
            </h2>
            <p className="text-xl text-neutral-400 max-w-2xl mx-auto">
              Powerful tools and features to help you plan, build, and share your car modifications
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <div 
                key={feature.id}
                className="card group animate-slideInUp"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className="flex items-center space-x-4 mb-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center text-white group-hover:scale-110 transition-transform duration-300">
                    {feature.icon}
                  </div>
                  <h3 className="text-xl font-semibold text-white">{feature.title}</h3>
                </div>
                <p className="text-neutral-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto">
          <div className="glass-card rounded-2xl p-8 md:p-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
              <div className="animate-slideInLeft">
                <div className="text-4xl md:text-5xl font-bold text-primary-400 mb-2">10K+</div>
                <div className="text-neutral-400">Active Users</div>
              </div>
              <div className="animate-slideInUp">
                <div className="text-4xl md:text-5xl font-bold text-primary-400 mb-2">50K+</div>
                <div className="text-neutral-400">Parts Listed</div>
              </div>
              <div className="animate-slideInRight">
                <div className="text-4xl md:text-5xl font-bold text-primary-400 mb-2">100K+</div>
                <div className="text-neutral-400">Build Lists Created</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto text-center">
          <div className="max-w-3xl mx-auto animate-slideInUp">
            <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-white to-neutral-300 bg-clip-text text-transparent">
              Ready to Start Building?
            </h2>
            <p className="text-xl text-neutral-400 mb-8">
              Join the community and start creating amazing car modifications today
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              {isAuthenticated ? (
                <>
                  <LinkButton to="/builder" size="lg">
                    <BsTools className="mr-2" />
                    Create Build List
                  </LinkButton>
                  <LinkButton to="/global-parts" variant="outline" size="lg">
                    <FaCogs className="mr-2" />
                    Explore Parts
                  </LinkButton>
                </>
              ) : (
                <>
                  <LinkButton to="/register" size="lg">
                    <GiRaceCar className="mr-2" />
                    Join Free
                  </LinkButton>
                  <LinkButton to="/about" variant="outline" size="lg">
                    <FaUsers className="mr-2" />
                    Learn More
                  </LinkButton>
                </>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
