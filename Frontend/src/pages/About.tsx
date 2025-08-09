import LoadingSpinner from '../components/common/LoadingSpinner';

function About() {
  return (
    <div className="container mx-auto p-4 text-center">
      <h1 className="text-4xl font-bold mb-6">About CarModPicker</h1>
      <p className="text-lg mb-4">
        CarModPicker is your ultimate platform for discovering, planning, and
        sharing car modifications.
      </p>
      <p className="text-lg mb-4">
        Whether you're a car enthusiast looking to customize your ride or just
        starting out, we provide the tools and community to help you build your
        dream car.
      </p>
      <LoadingSpinner />
    </div>
  );
}
export default About;
