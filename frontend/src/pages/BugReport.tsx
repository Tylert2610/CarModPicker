import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { bugReportsApi } from '../api/bug_reports';
import type { BugReportCreate } from '../types/Api';

import { ErrorAlert, SuccessAlert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import PageHeader from '../components/layout/PageHeader';

// Utility functions to detect browser and device info
const detectBrowserInfo = (): string => {
  const userAgent = navigator.userAgent;
  let browserName = 'Unknown';
  let browserVersion = 'Unknown';

  // Detect browser
  if (userAgent.indexOf('Firefox') > -1) {
    browserName = 'Firefox';
    const match = userAgent.match(/Firefox\/(\d+)/);
    browserVersion = match?.[1] ?? 'Unknown';
  } else if (
    userAgent.indexOf('Chrome') > -1 &&
    userAgent.indexOf('Edg') === -1
  ) {
    browserName = 'Chrome';
    const match = userAgent.match(/Chrome\/(\d+)/);
    browserVersion = match?.[1] ?? 'Unknown';
  } else if (
    userAgent.indexOf('Safari') > -1 &&
    userAgent.indexOf('Chrome') === -1
  ) {
    browserName = 'Safari';
    const match = userAgent.match(/Version\/(\d+)/);
    browserVersion = match?.[1] ?? 'Unknown';
  } else if (userAgent.indexOf('Edg') > -1) {
    browserName = 'Edge';
    const match = userAgent.match(/Edg\/(\d+)/);
    browserVersion = match?.[1] ?? 'Unknown';
  } else if (userAgent.indexOf('Opera') > -1 || userAgent.indexOf('OPR') > -1) {
    browserName = 'Opera';
    const match = userAgent.match(/(?:Opera|OPR)\/(\d+)/);
    browserVersion = match?.[1] ?? 'Unknown';
  }

  return `${browserName} ${browserVersion}`;
};

const detectDeviceInfo = (): string => {
  const userAgent = navigator.userAgent;
  let os = 'Unknown';
  let deviceType = '';

  // Detect OS
  if (userAgent.indexOf('Win') > -1) {
    if (userAgent.indexOf('Windows NT 10.0') > -1) os = 'Windows 10/11';
    else if (userAgent.indexOf('Windows NT 6.3') > -1) os = 'Windows 8.1';
    else if (userAgent.indexOf('Windows NT 6.2') > -1) os = 'Windows 8';
    else if (userAgent.indexOf('Windows NT 6.1') > -1) os = 'Windows 7';
    else os = 'Windows';
  } else if (userAgent.indexOf('Mac') > -1) {
    const match = userAgent.match(/Mac OS X (\d+)[._](\d+)/);
    if (match) {
      os = `macOS ${match[1]}.${match[2]}`;
    } else {
      os = 'macOS';
    }
  } else if (userAgent.indexOf('Linux') > -1) {
    os = 'Linux';
  } else if (userAgent.indexOf('Android') > -1) {
    const match = userAgent.match(/Android (\d+(?:\.\d+)?)/);
    os = match?.[1] ? `Android ${match[1]}` : 'Android';
  } else if (
    userAgent.indexOf('iOS') > -1 ||
    userAgent.indexOf('iPhone') > -1 ||
    userAgent.indexOf('iPad') > -1
  ) {
    const match = userAgent.match(/OS (\d+)[._](\d+)/);
    if (match) {
      os = `iOS ${match[1]}.${match[2]}`;
    } else {
      os = 'iOS';
    }
  }

  // Detect device type
  if (
    userAgent.indexOf('Mobile') > -1 ||
    userAgent.indexOf('iPhone') > -1 ||
    userAgent.indexOf('Android') > -1
  ) {
    deviceType = 'Mobile';
  } else if (
    userAgent.indexOf('Tablet') > -1 ||
    userAgent.indexOf('iPad') > -1
  ) {
    deviceType = 'Tablet';
  } else {
    deviceType = 'Desktop';
  }

  return `${os} (${deviceType})`;
};

function BugReport() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<BugReportCreate>({
    title: '',
    description: '',
    steps_to_reproduce: '',
    expected_behavior: '',
    actual_behavior: '',
    browser_info: '',
    device_info: '',
    screenshot_url: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Auto-detect browser and device info on component mount
  useEffect(() => {
    const browserInfo = detectBrowserInfo();
    const deviceInfo = detectDeviceInfo();
    setFormData((prev) => ({
      ...prev,
      browser_info: browserInfo,
      device_info: deviceInfo,
    }));
  }, []);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    // Validation
    if (!formData.title.trim()) {
      setError('Title is required');
      return;
    }
    if (!formData.description.trim()) {
      setError('Description is required');
      return;
    }

    setIsSubmitting(true);

    try {
      // Clean up empty strings to null
      const submitData: BugReportCreate = {
        title: formData.title.trim(),
        description: formData.description.trim(),
        steps_to_reproduce: formData.steps_to_reproduce?.trim() || null,
        expected_behavior: formData.expected_behavior?.trim() || null,
        actual_behavior: formData.actual_behavior?.trim() || null,
        browser_info: formData.browser_info?.trim() || null,
        device_info: formData.device_info?.trim() || null,
        screenshot_url: formData.screenshot_url?.trim() || null,
      };

      await bugReportsApi.createBugReport(submitData);
      setSuccess(true);
      // Reset form
      setFormData({
        title: '',
        description: '',
        steps_to_reproduce: '',
        expected_behavior: '',
        actual_behavior: '',
        browser_info: '',
        device_info: '',
        screenshot_url: '',
      });
      // Redirect after 2 seconds
      setTimeout(() => {
        void navigate('/');
      }, 2000);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to submit bug report. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Report a Bug"
        subtitle="Help us improve by reporting bugs and issues"
      />

      <Card className="max-w-3xl mx-auto">
        {success && (
          <SuccessAlert message="Bug report submitted successfully! Redirecting..." />
        )}
        {error && <ErrorAlert message={error} />}

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
          <div>
            <label
              htmlFor="title"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Title *
            </label>
            <Input
              id="title"
              name="title"
              type="text"
              value={formData.title}
              onChange={handleInputChange}
              placeholder="Brief description of the bug"
              required
              disabled={isSubmitting}
            />
          </div>

          <div>
            <label
              htmlFor="description"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Description *
            </label>
            <Textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Detailed description of the bug"
              required
              disabled={isSubmitting}
              rows={6}
              className="resize-none"
            />
          </div>

          <div>
            <label
              htmlFor="steps_to_reproduce"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Steps to Reproduce (Optional)
            </label>
            <Textarea
              id="steps_to_reproduce"
              name="steps_to_reproduce"
              value={formData.steps_to_reproduce || ''}
              onChange={handleInputChange}
              placeholder="1. Go to...&#10;2. Click on...&#10;3. See error..."
              disabled={isSubmitting}
              rows={4}
              className="resize-none"
            />
          </div>

          <div>
            <label
              htmlFor="expected_behavior"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Expected Behavior (Optional)
            </label>
            <Textarea
              id="expected_behavior"
              name="expected_behavior"
              value={formData.expected_behavior || ''}
              onChange={handleInputChange}
              placeholder="What should have happened?"
              disabled={isSubmitting}
              rows={3}
              className="resize-none"
            />
          </div>

          <div>
            <label
              htmlFor="actual_behavior"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Actual Behavior (Optional)
            </label>
            <Textarea
              id="actual_behavior"
              name="actual_behavior"
              value={formData.actual_behavior || ''}
              onChange={handleInputChange}
              placeholder="What actually happened?"
              disabled={isSubmitting}
              rows={3}
              className="resize-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="browser_info"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Browser Info (Auto-detected)
              </label>
              <Input
                id="browser_info"
                name="browser_info"
                type="text"
                value={formData.browser_info || ''}
                onChange={handleInputChange}
                placeholder="Auto-detected"
                disabled={true}
              />
              <div className="mt-2 text-sm text-muted-foreground">
                Automatically detected from your browser
              </div>
            </div>

            <div>
              <label
                htmlFor="device_info"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Device Info (Auto-detected)
              </label>
              <Input
                id="device_info"
                name="device_info"
                type="text"
                value={formData.device_info || ''}
                onChange={handleInputChange}
                placeholder="Auto-detected"
                disabled={true}
              />
              <div className="mt-2 text-sm text-muted-foreground">
                Automatically detected from your device
              </div>
            </div>
          </div>

          <div>
            <label
              htmlFor="screenshot_url"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Screenshot URL (Optional)
            </label>
            <Input
              id="screenshot_url"
              name="screenshot_url"
              type="url"
              value={formData.screenshot_url || ''}
              onChange={handleInputChange}
              placeholder="https://example.com/screenshot.png"
              disabled={isSubmitting}
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void navigate('/')}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={isSubmitting}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Submitting...' : 'Submit Bug Report'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

export default BugReport;
