import { Link } from 'react-router-dom';

import { useDocumentMeta } from '../hooks/useDocumentMeta';

const LAST_UPDATED = 'April 15, 2026';
const CONTACT_EMAIL = 'tyler@webbpulse.com';
const GOVERNING_STATE = 'California';

/** Static terms of service page. */
function TermsOfService() {
  useDocumentMeta({
    title: 'Terms of Service',
    description:
      'Read the CarModPicker Terms of Service — the rules for using the platform, user responsibilities, and content policies.',
    canonicalPath: '/terms-of-service',
  });
  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 md:p-12">
        <h1 className="text-4xl md:text-5xl font-bold mb-2">
          <span className="text-gradient">Terms of Service</span>
        </h1>
        <p className="text-muted-foreground text-sm mb-8">
          Last updated: {LAST_UPDATED}
        </p>

        <div className="prose prose-invert max-w-none text-foreground space-y-6 leading-relaxed">
          <p>
            Please read these Terms of Service ("Terms") carefully before using
            CarModPicker (the "Service"). By creating an account or otherwise
            using the Service, you agree to be bound by these Terms and by our{' '}
            <Link to="/privacy-policy" className="text-primary underline">
              Privacy Policy
            </Link>
            . If you do not agree, do not use the Service.
          </p>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              1. The Service
            </h2>
            <p>
              CarModPicker is a hobbyist web application operated by an
              individual that lets users catalog cars, build lists, and parts,
              and share build logs. It is offered in active development and on a
              best-effort basis. Features may change or disappear without
              notice.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              2. Eligibility and Accounts
            </h2>
            <p>
              <strong>
                The Service is intended for adults only. You must be at least 18
                years old to create an account or otherwise use the Service.
              </strong>{' '}
              By using the Service, you represent and warrant that you are 18 or
              older. The Service is not directed to, and we do not knowingly
              collect personal information from, anyone under 18. If we learn
              that an account belongs to someone under 18, we will terminate it
              and delete the associated data.
            </p>
            <p>
              You are responsible for maintaining the security of your account
              credentials and for all activity under your account. Provide
              accurate information when registering.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              3. User Content
            </h2>
            <p>
              "Your Content" means anything you submit to the Service, including
              cars, build lists, parts, build logs, images, votes, and comments.
              You retain ownership of Your Content. By submitting it, you grant
              us a worldwide, non-exclusive, royalty-free license to host,
              store, reproduce, display, adapt, and distribute Your Content for
              the purpose of operating and promoting the Service.
            </p>
            <p>
              You represent that you have the rights necessary to grant this
              license and that Your Content does not infringe anyone else's
              rights or violate any law.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              4. Acceptable Use
            </h2>
            <p>You agree not to:</p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                Use the Service for anything illegal, abusive, harassing,
                hateful, or that infringes others' rights.
              </li>
              <li>
                Upload malware, spam, deceptive content, or content containing
                others' personal information without permission.
              </li>
              <li>
                Attempt to break, overload, probe, scrape, or reverse engineer
                the Service outside of its intended interfaces, or circumvent
                rate limits, access controls, or security measures.
              </li>
              <li>
                Impersonate another person or misrepresent your affiliation with
                anyone.
              </li>
              <li>
                Use automated systems (bots, crawlers) against the Service
                except through interfaces we explicitly provide for that
                purpose.
              </li>
            </ul>
            <p>
              We may remove content or take other action if we believe, in our
              sole discretion, that it violates these Terms or is otherwise
              harmful.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              5. No Guarantee of Availability or Data Retention
            </h2>
            <p>
              The Service is provided on an "as is" and "as available" basis. We
              do not guarantee that the Service will be uninterrupted, timely,
              error-free, secure, or that any data you submit will be preserved.
            </p>
            <p>
              We reserve the right, at any time and without notice or liability,
              to:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                Reset, migrate, wipe, or delete the database, user-uploaded
                images, accounts, or any other stored content — in whole or in
                part.
              </li>
              <li>
                Suspend, modify, or discontinue the Service or any feature.
              </li>
              <li>
                Terminate or suspend any account, for any reason or no reason.
              </li>
            </ul>
            <p>
              <strong>
                Keep your own copies of anything you care about. Do not rely on
                the Service as a system of record.
              </strong>
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              6. Third-Party Content and Links
            </h2>
            <p>
              The Service may display or link to content from third parties (for
              example, retailer product pages, part images, and advertising). We
              do not endorse and are not responsible for third-party content,
              products, or services, and your dealings with any third party are
              solely between you and them.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              7. Paid Features and Billing
            </h2>
            <p>
              Some features of the Service may require payment ("Paid
              Features"). If you sign up for a Paid Feature:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                You authorize us (or our payment processor) to charge the
                payment method you provide for all stated fees and applicable
                taxes.
              </li>
              <li>
                Subscriptions renew automatically at the then-current rate at
                the end of each billing period until you cancel. You may cancel
                at any time through your account settings; cancellation takes
                effect at the end of the current billing period.
              </li>
              <li>
                All fees are non-refundable except where required by law or
                where we explicitly offer a refund. We do not issue prorated
                refunds for partial periods or unused time.
              </li>
              <li>
                We may change fees, Paid Features, or billing terms at any time.
                Changes take effect at the start of your next billing period.
                Your continued use of a Paid Feature after the change is your
                agreement to the new terms.
              </li>
              <li>
                If a payment fails, we may suspend, downgrade, or terminate
                access to Paid Features until the issue is resolved.
              </li>
              <li>
                Benefits of Paid Features (e.g. ad-free browsing, premium perks)
                may be modified or removed at any time as the Service evolves.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              8. Disclaimers
            </h2>
            <p>
              TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE SERVICE IS PROVIDED
              "AS IS" AND "AS AVAILABLE," WITHOUT WARRANTIES OF ANY KIND,
              WHETHER EXPRESS, IMPLIED, OR STATUTORY, INCLUDING WARRANTIES OF
              MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE,
              NON-INFRINGEMENT, ACCURACY, OR UNINTERRUPTED OR ERROR-FREE
              OPERATION. ANY PART COMPATIBILITY, FITMENT, PRICING, OR OTHER DATA
              IS USER-SUBMITTED AND NOT VERIFIED — DO NOT RELY ON IT FOR
              SAFETY-CRITICAL DECISIONS. VERIFY INDEPENDENTLY BEFORE PURCHASING
              OR INSTALLING PARTS.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              9. Limitation of Liability
            </h2>
            <p>
              TO THE MAXIMUM EXTENT PERMITTED BY LAW, IN NO EVENT WILL
              CARMODPICKER OR ITS OPERATOR BE LIABLE FOR ANY INDIRECT,
              INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY
              LOSS OF PROFITS, REVENUES, DATA, GOODWILL, OR OTHER INTANGIBLE
              LOSSES, ARISING OUT OF OR RELATED TO YOUR USE OF (OR INABILITY TO
              USE) THE SERVICE. OUR TOTAL LIABILITY FOR ALL CLAIMS RELATING TO
              THE SERVICE WILL NOT EXCEED USD $100 OR THE AMOUNT YOU PAID US IN
              THE TWELVE MONTHS BEFORE THE CLAIM, WHICHEVER IS GREATER.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              10. Indemnification
            </h2>
            <p>
              You agree to defend, indemnify, and hold harmless CarModPicker and
              its operator from any claims, damages, liabilities, and expenses
              (including reasonable attorneys' fees) arising out of your use of
              the Service, Your Content, or your violation of these Terms or of
              any law or third-party right.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">11. DMCA</h2>
            <p>
              If you believe material on the Service infringes your copyright,
              send a DMCA notice to{' '}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-primary underline"
              >
                {CONTACT_EMAIL}
              </a>
              . We will respond to valid notices as required by law and may
              remove the content and terminate repeat infringers.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              12. Termination
            </h2>
            <p>
              You may stop using the Service at any time. We may suspend or
              terminate your access at any time, with or without cause or
              notice. Sections that by their nature should survive termination
              (including User Content, No Guarantee of Availability, Paid
              Features, Disclaimers, Limitation of Liability, Indemnification,
              Governing Law, and General) will survive.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              13. Governing Law and Venue
            </h2>
            <p>
              Before filing any formal claim, you agree to contact us at{' '}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-primary underline"
              >
                {CONTACT_EMAIL}
              </a>{' '}
              and attempt to resolve the dispute informally for at least sixty
              (60) days.
            </p>
            <p>
              These Terms are governed by the laws of the State of{' '}
              {GOVERNING_STATE}, United States, without regard to its
              conflict-of-laws rules. You agree that any dispute arising out of
              or relating to these Terms or the Service will be resolved
              exclusively in the state or federal courts located in{' '}
              {GOVERNING_STATE}, and you consent to personal jurisdiction there.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              14. Changes to These Terms
            </h2>
            <p>
              We may update these Terms at any time. Material changes will be
              reflected by updating the "Last updated" date above and, where
              appropriate, by notice through the Service or by email. Continued
              use of the Service after a change means you accept the updated
              Terms.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              15. General
            </h2>
            <ul className="list-disc list-inside space-y-2 ml-2">
              <li>
                <strong>Entire agreement.</strong> These Terms, together with
                the Privacy Policy, are the entire agreement between you and us
                regarding the Service and supersede any prior agreements.
              </li>
              <li>
                <strong>Severability.</strong> If any provision of these Terms
                is found unenforceable, the remaining provisions will remain in
                full force and effect.
              </li>
              <li>
                <strong>No waiver.</strong> Our failure to enforce any right or
                provision is not a waiver of that right or provision.
              </li>
              <li>
                <strong>Assignment.</strong> You may not assign or transfer
                these Terms or your account without our prior written consent.
                We may assign these Terms, in whole or in part, without
                restriction.
              </li>
              <li>
                <strong>Notices.</strong> We may give notices through the
                Service, by email, or by posting on the Site. Notices to us
                should be sent to{' '}
                <a
                  href={`mailto:${CONTACT_EMAIL}`}
                  className="text-primary underline"
                >
                  {CONTACT_EMAIL}
                </a>
                .
              </li>
              <li>
                <strong>No agency.</strong> No joint venture, partnership,
                employment, or agency relationship is created by these Terms.
              </li>
              <li>
                <strong>Export and sanctions.</strong> You represent that you
                are not located in a country subject to a U.S. government
                embargo, and are not on any U.S. government restricted-party
                list.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white mb-3">
              16. Contact
            </h2>
            <p>
              Questions about these Terms? Email{' '}
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

export default TermsOfService;
