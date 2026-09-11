import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';

/** Admin landing page linking to each administrative area. */
function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

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

  const adminSections = [
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
      title: 'Bug Reports',
      description: 'Review and manage bug reports',
      icon: '🐛',
      path: '/admin/bug-reports',
    },
    {
      title: 'Crawler & Jobs',
      description:
        'Run crawlers, manage archives, schedule, and background jobs',
      icon: '🕷️',
      path: '/admin/crawler',
    },
    {
      title: 'Parts Curation',
      description:
        'Inspect canonical link groups, promote/unlink duplicates, and rescan the catalog',
      icon: '🔗',
      path: '/admin/parts-curation',
    },
    {
      title: 'System & Database',
      description:
        'Migrations, data initialization, and destructive operations',
      icon: '⚙️',
      path: '/admin/system',
    },
    {
      title: 'System Statistics',
      description: 'Entity counts, storage usage, and catalog breakdowns',
      icon: '📊',
      path: '/admin/statistics',
    },
    {
      title: 'Extraction Health',
      description:
        'Adapter compliance, per-tier coverage, and 7d failure rates',
      icon: '🩺',
      path: '/admin/extraction-health',
    },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Admin Dashboard"
        subtitle="Manage CarModPicker system settings and content"
      />

      {/* Navigation cards */}
      <Card>
        <SectionHeader title="Admin Sections" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {adminSections.map((section) => (
            <div
              key={section.path}
              className="p-4 border border-gray-700 rounded-lg hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center space-x-3 mb-2">
                <span className="text-2xl">{section.icon}</span>
                <h3 className="text-lg font-semibold text-gray-200">
                  {section.title}
                </h3>
              </div>
              <p className="text-gray-400 mb-3 text-sm">
                {section.description}
              </p>
              <Button
                onClick={() => void navigate(section.path)}
                className="w-full"
              >
                {section.title}
              </Button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default AdminDashboard;
