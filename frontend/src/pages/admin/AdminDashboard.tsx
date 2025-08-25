import { useAuth } from '../../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';

function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Admin Dashboard" />
        <Card>
          <ErrorAlert message="Please log in to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Admin Dashboard" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  const adminFeatures = [
    {
      title: 'Category Management',
      description: 'Create, edit, and manage part categories',
      icon: '📂',
      path: '/admin/categories',
    },
    {
      title: 'User Management',
      description: 'View and manage user accounts',
      icon: '👥',
      path: '/admin/users',
    },
    {
      title: 'Report Review',
      description: 'Review and manage part reports',
      icon: '🚨',
      path: '/admin/reports',
    },
    {
      title: 'Flagged Parts',
      description: 'Review parts flagged by the voting system',
      icon: '⚠️',
      path: '/admin/flagged-parts',
    },
  ];

  return (
    <div>
      <PageHeader
        title="Admin Dashboard"
        subtitle="Manage CarModPicker system settings and content"
      />

      <Card>
        <SectionHeader title="Admin Functions" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {adminFeatures.map((feature) => (
            <div
              key={feature.path}
              className="p-4 border border-gray-700 rounded-lg hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center space-x-3 mb-2">
                <span className="text-2xl">{feature.icon}</span>
                <h3 className="text-lg font-semibold text-gray-200">
                  {feature.title}
                </h3>
              </div>
              <p className="text-gray-400 mb-3">{feature.description}</p>
              <ActionButton
                onClick={() => void navigate(feature.path)}
                className="w-full"
              >
                Access {feature.title}
              </ActionButton>
            </div>
          ))}
        </div>
      </Card>

      <div className="mt-6">
        <Card>
          <SectionHeader title="Quick Stats" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="text-2xl font-bold text-blue-400">Admin</div>
              <div className="text-gray-400">Dashboard</div>
            </div>
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="text-2xl font-bold text-green-400">System</div>
              <div className="text-gray-400">Management</div>
            </div>
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="text-2xl font-bold text-yellow-400">Content</div>
              <div className="text-gray-400">Moderation</div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default AdminDashboard;
