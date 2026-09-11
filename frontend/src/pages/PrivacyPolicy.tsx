import { Link } from 'react-router-dom';

import { useDocumentMeta } from '../hooks/useDocumentMeta';

const LAST_UPDATED = 'April 18, 2026';
const CONTACT_EMAIL = 'tyler@webbpulse.com';

/** Static privacy policy page. */
function PrivacyPolicy() {
  useDocumentMeta({
    title: 'Privacy Policy',
    description:
      "Read CarModPicker's privacy policy: what data we collect, how we use it, and your rights regarding your personal information.",
    canonicalPath: '/privacy-policy',
  });
  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 md:p-12">
        <h1 className="text-4xl md:text-5xl font-bold mb-2">
          <span className="text-gradient">Privacy Policy</span>
        </h1>
        <p className="text-muted-foreground text-sm mb-8">
          Last updated: {LAST_UPDATED}
        </p>

        <div className="prose prose-invert max-w-none text-foreground space-y-6 leading-relaxed">
          <p>
            CarModPicker ("we", "us", "the Service") is a hobbyist project
            operated by an individual. This policy describes, in plain terms,
            what data we handle and what you should reasonably expect. By using
            the Service you agree to this policy and to our{' '}
            <Link to="/terms-of-service" className="text-primary underline">
              Terms of Service
            </Link>
            .
          </p>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              1. Information We Collect
            </h2>
            <p>We collect only what is needed to run the Service:</p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                <strong>Account information</strong> you provide: username,
                email address, hashed password, optional profile details, and
                two-factor authentication secrets if enabled.
              </li>
              <li>
                <strong>Content you create</strong>: cars, build lists, parts,
                build logs, images you upload, votes, and comments. Items you
                submit privately — such as content reports to moderators and bug
                reports — are kept internal and are not displayed publicly.
              </li>
              <li>
                <strong>Technical data</strong>: IP address, user agent,
                timestamps, and request logs used for security, rate limiting,
                and debugging.
              </li>
              <li>
                <strong>Cookies and local storage</strong>: a session token to
                keep you logged in, plus minimal preferences. We do not use
                tracking cookies of our own.
              </li>
              <li>
                <strong>Data from our Chrome extension</strong>: if you install
                our optional extension, it does <em>not</em> run in the
                background and does <em>not</em> passively track your browsing
                history. When — and only when — you click the extension's action
                button on a page, it captures that page's URL and its rendered
                HTML and sends them to our servers for parsing into product
                information. Before the HTML is stored or parsed, our servers
                remove scripts (other than product structured data), styles,
                iframes, and form field values so that autofilled inputs and
                inline user-state blobs are not retained. The extension does not
                read cookies, browser storage, or request headers.
              </li>
              <li>
                <strong>Google Sign-In</strong>: if you choose to sign in with
                Google, we receive your Google account email address and basic
                profile information (name, profile picture) from Google to
                create or authenticate your account. We do not request access to
                any other Google APIs, Drive, Gmail, Calendar, or contacts. Our
                use of information received from Google APIs adheres to the{' '}
                <a
                  href="https://developers.google.com/terms/api-services-user-data-policy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline"
                >
                  Google API Services User Data Policy
                </a>
                , including the Limited Use requirements.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              2. How We Use Your Information
            </h2>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>To operate, maintain, and improve the Service.</li>
              <li>
                To authenticate you and send transactional email (e.g. email
                verification, password reset).
              </li>
              <li>
                To detect, prevent, and investigate abuse, fraud, and security
                issues.
              </li>
              <li>
                To display user-submitted content (usernames, builds, parts,
                comments) publicly on the Service. Assume anything you post
                publicly is public. Content you submit privately — such as
                moderation reports and bug reports — is used only for operations
                and is not displayed to other users.
              </li>
            </ul>
            <p>
              We do not sell your personal information. We do not share it with
              third parties except as described below.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              3. Third-Party Services
            </h2>
            <p>
              We rely on third-party providers to help operate the Service.
              These providers may process limited data on our behalf or as part
              of serving the Service, including:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                <strong>Cloud infrastructure providers</strong> — for hosting,
                storage, and transactional email.
              </li>
              <li>
                <strong>Advertising partners</strong> — third-party vendors,
                including Google, may use cookies to serve ads based on your
                prior visits to our Service or other websites. Google's use of
                advertising cookies enables it and its partners to serve ads to
                you. You can opt out of personalized advertising by visiting{' '}
                <a
                  href="https://www.google.com/settings/ads"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline"
                >
                  Google Ads Settings
                </a>{' '}
                or, for other participating vendors,{' '}
                <a
                  href="https://www.aboutads.info/choices"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline"
                >
                  aboutads.info/choices
                </a>
                .
              </li>
              <li>
                <strong>Retailer websites</strong> — if you use features that
                link to or interact with retailer pages, your interaction with
                those sites is governed by their own policies.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              4. Chrome Extension: Limited Use of Data
            </h2>
            <p>
              Our Chrome extension is built to comply with the{' '}
              <a
                href="https://developer.chrome.com/docs/webstore/program-policies/limited-use/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                Chrome Web Store User Data Policy
              </a>
              , including the Limited Use requirements. Specifically:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                Data captured by the extension (the URL and sanitized HTML of
                the page you explicitly capture) is used <strong>only</strong>{' '}
                to parse product information for you and to let you add that
                part to your CarModPicker account.
              </li>
              <li>
                We do not sell or transfer this data to third parties for
                advertising, resale, marketing, credit-scoring, or any unrelated
                purpose.
              </li>
              <li>
                We do not use this data for personalized advertising of any
                kind.
              </li>
              <li>
                We do not allow humans to read this data except: (a) with your
                explicit consent, (b) to investigate security incidents or
                policy abuse, (c) to comply with applicable law, or (d) where
                the data has been aggregated or anonymized such that it no
                longer identifies you.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              5. Data Retention and Deletion
            </h2>
            <p>
              We do <strong>not</strong> guarantee any particular retention
              period for your data. The Service is in active development and is
              operated on a best-effort basis. We may, at any time and without
              prior notice, reset, migrate, wipe, or delete accounts, databases,
              uploaded images, or any other stored content — for example:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>during schema changes or infrastructure moves;</li>
              <li>during abuse cleanup or moderation actions;</li>
              <li>or simply because we decide to.</li>
            </ul>
            <p>
              <strong>Captured page archives.</strong> Sanitized HTML captured
              via the Chrome extension is stored so that the parsed product
              information can be refreshed or corrected later. We retain it only
              for as long as it remains useful for that purpose, and we may
              delete or overwrite it at any time without notice — for example:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>when the associated part is removed;</li>
              <li>
                when an archive is superseded by a newer capture of the same
                URL;
              </li>
              <li>or during routine storage cleanup.</li>
            </ul>
            <p>
              You can request deletion of pages you submitted by emailing us.
            </p>
            <p>
              You should keep your own copies of anything you care about. Do not
              rely on the Service as a system of record.
            </p>
            <p>
              You can request deletion of your account and associated personal
              data by emailing{' '}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-primary underline"
              >
                {CONTACT_EMAIL}
              </a>
              . We will process verified deletion requests without undue delay,
              typically within thirty (30) days. Content you posted publicly may
              persist in backups or caches for a reasonable period after
              deletion.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              6. Security
            </h2>
            <p>
              We take reasonable steps to protect your data, including hashing
              stored passwords, encrypting traffic in transit, and offering
              optional two-factor authentication. No system is perfectly secure,
              and we make no guarantee that your data will not be accessed,
              disclosed, altered, or destroyed as a result of a breach. Use a
              unique password.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              7. Minors
            </h2>
            <p>
              <strong>
                The Service is intended exclusively for adults 18 years of age
                and older.
              </strong>{' '}
              We do not direct the Service to minors and do not knowingly
              collect personal information from anyone under 18. If you believe
              a minor has provided us personal information, contact us at{' '}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-primary underline"
              >
                {CONTACT_EMAIL}
              </a>{' '}
              and we will terminate the account and delete the data.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              8. EEA / UK Residents (GDPR / UK GDPR)
            </h2>
            <p>
              If you are located in the European Economic Area or the United
              Kingdom, we process your personal data on the following legal
              bases:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                <strong>Performance of a contract</strong> — to provide the
                Service you signed up for (e.g. authenticate you, display your
                builds).
              </li>
              <li>
                <strong>Legitimate interests</strong> — to secure the Service,
                prevent abuse, debug issues, improve features, and send
                operational communications.
              </li>
              <li>
                <strong>Consent</strong> — where we rely on your consent (for
                example, optional cookies for personalized advertising). You may
                withdraw consent at any time.
              </li>
              <li>
                <strong>Legal obligation</strong> — to comply with applicable
                law.
              </li>
            </ul>
            <p>
              You have the right to access, correct, export, restrict, object
              to, or delete your personal data, and to lodge a complaint with
              your local data protection authority. To exercise any of these
              rights, email us. We will respond within one month.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              9. California Residents (CCPA / CPRA)
            </h2>
            <p>
              In the past twelve months, we have collected the following
              categories of personal information from California residents:
              identifiers (e.g. username, email, IP address), customer account
              records, commercial information (if you purchase paid features),
              internet and network activity (e.g. request logs), and
              user-generated content.
            </p>
            <p>
              <strong>
                We do not sell or share your personal information for
                cross-context behavioral advertising, and we have not done so in
                the past twelve months.
              </strong>{' '}
              We do not knowingly collect or sell the personal information of
              minors under 16.
            </p>
            <p>
              California residents have the right to know, delete, correct, and
              limit the use of their personal information, and to not be
              discriminated against for exercising these rights. To exercise any
              of these rights, email us.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              10. International Users
            </h2>
            <p>
              The Service is operated from the United States and your data will
              be processed there. By using the Service, you consent to that
              transfer.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              11. Changes to This Policy
            </h2>
            <p>
              We may update this policy at any time. Material changes will be
              reflected by updating the "Last updated" date above. Continued use
              of the Service after a change means you accept the updated policy.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              12. Contact
            </h2>
            <p>
              Questions about this policy? Email{' '}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-primary underline"
              >
                {CONTACT_EMAIL}
              </a>
              .
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export default PrivacyPolicy;
