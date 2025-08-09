import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import { ErrorAlert, ConfirmationAlert } from '../../components/common/Alerts';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';

function VerifyEmailConfirm() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const statusParam = searchParams.get('status');
    const messageParam = searchParams.get('message');

    if (statusParam) {
      setStatus(statusParam);
    }
    if (messageParam) {
      setMessage(messageParam);
    }
  }, [searchParams]);

  return (
    <AuthCard title="Email Verification Result">
      <div>
        {status === 'success' && <ConfirmationAlert message={message} />}
        {status === 'info' && <ConfirmationAlert message={message} />}
        {status === 'error' && <ErrorAlert message={message} />}
        {!status && (
          <>
            <ErrorAlert message="Invalid or missing verification link. Please request a new verification email if needed." />
            <AuthRedirectLink
              text="Request a new"
              linkText="Verification Email"
              to="/verify-email"
            />
          </>
        )}
        {status && <AuthRedirectLink text="Back to" linkText="Home" to="/" />}
      </div>
    </AuthCard>
  );
}
export default VerifyEmailConfirm;
