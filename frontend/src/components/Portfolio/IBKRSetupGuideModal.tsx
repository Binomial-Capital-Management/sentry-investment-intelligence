/**
 * IBKR Setup Guide Modal - Clean, detailed guide for connecting IBKR accounts
 */

import React, { useState } from 'react';
import { X, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';

interface IBKRSetupGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const IBKRSetupGuideModal: React.FC<IBKRSetupGuideModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [currentPage, setCurrentPage] = useState(0);

  if (!isOpen) return null;

  const pages = [
    // Page 1: Overview
    {
      title: 'Connect Your IBKR Account',
      subtitle: 'One-time setup • 5-10 minutes',
      content: (
        <div className="space-y-8">
          <p className="text-gray-600 leading-relaxed">
            Connect your Interactive Brokers account to automatically sync your positions,
            trades, and cash balances. This uses IBKR's official Flex Query API — a secure,
            read-only connection that cannot place trades or move funds.
          </p>

          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Before you begin</h4>
            <ul className="space-y-2.5 text-sm text-gray-600">
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0" />
                <span>An active IBKR account (live or paper trading)</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0" />
                <span>Access to IBKR's web portal (Account Management) — not the mobile app or Trader Workstation</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0" />
                <span>Your IBKR login credentials and any two-factor authentication device</span>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">What you'll get</h4>
            <ul className="space-y-2.5 text-sm text-gray-600">
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                <span>Automatic portfolio sync twice daily (12 PM and 5:30 PM ET)</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                <span>All positions with cost basis, quantities, and current market values</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                <span>Complete trade history for AI-powered post-mortem analysis</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                <span>Cash balances across all currencies</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                <span>Manual sync anytime via the "Sync IBKR" button</span>
              </li>
            </ul>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-500">
              <strong>Security:</strong> Your credentials are encrypted with AES-256. We only have read access —
              we cannot place orders, transfer funds, or modify your account. You can revoke access anytime from IBKR's website.
            </p>
          </div>
        </div>
      ),
    },

    // Page 2: Log In & Navigate
    {
      title: 'Access Flex Queries',
      subtitle: 'Step 1 of 4',
      content: (
        <div className="space-y-6">
          <p className="text-gray-600 leading-relaxed">
            First, log into IBKR's Account Management portal and navigate to the Flex Queries section.
          </p>

          <div className="space-y-5">
            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">1</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Open IBKR's website</p>
                <a
                  href="https://www.interactivebrokers.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline inline-flex items-center gap-1"
                >
                  www.interactivebrokers.com <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">2</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Click "Log In" in the top-right corner</p>
                <p className="text-xs text-gray-500">Enter your username, password, and complete any two-factor authentication</p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">3</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">You should now be in Account Management</p>
                <p className="text-xs text-gray-500">
                  Look for a sidebar menu with options like Home, Portfolio, Reports.
                  If you see a trading interface instead, look for "Account Management" or "Settings" link.
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">4</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Navigate to Flex Queries</p>
                <p className="text-xs text-gray-500 mb-2">In the left sidebar, click:</p>
                <div className="bg-gray-50 rounded-md px-3 py-2 text-sm font-mono text-gray-700">
                  Reports → Flex Queries
                </div>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-500">
              <strong>Can't find Flex Queries?</strong> Some account types have it under
              "Performance & Reports" or "Statements". You can also search for "Flex" in the portal's search bar.
            </p>
          </div>
        </div>
      ),
    },

    // Page 3: Create Flex Query
    {
      title: 'Create a Flex Query',
      subtitle: 'Step 2 of 4',
      content: (
        <div className="space-y-6">
          <p className="text-gray-600 leading-relaxed">
            A Flex Query is a custom report template that tells IBKR exactly what data to share.
            You'll create one that includes your positions, trades, and cash.
          </p>

          <div className="space-y-5">
            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">1</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Click the "+" or "Create" button</p>
                <p className="text-xs text-gray-500">Usually in the top-right area of the Flex Queries page</p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">2</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Select "Activity Flex Query"</p>
                <p className="text-xs text-gray-500">
                  <strong>Important:</strong> Choose "Activity Flex Query" — not "Trade Confirmation Flex Query".
                  Only Activity queries include the Open Positions section we need.
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">3</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Enter a query name</p>
                <p className="text-xs text-gray-500 mb-2">Any name you'll remember, for example:</p>
                <div className="bg-gray-50 rounded-md px-3 py-2 text-sm font-mono text-gray-700">
                  Sentry Portfolio Sync
                </div>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-500">
              <strong>Why Activity?</strong> Activity Flex Queries can include Open Positions (your current holdings),
              Trades (buy/sell history), and Cash Reports. Trade Confirmation queries only show individual trade confirmations.
            </p>
          </div>
        </div>
      ),
    },

    // Page 4: Configure Sections
    {
      title: 'Select Data Sections',
      subtitle: 'Step 3 of 4',
      content: (
        <div className="space-y-6">
          <p className="text-gray-600 leading-relaxed">
            Now configure which data to include. Find the "Sections" list and enable these three:
          </p>

          <div className="space-y-4">
            {/* Open Positions */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">Open Positions</p>
                  <p className="text-xs text-gray-500 mt-0.5">Shows all your current holdings</p>
                </div>
                <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded">Required</span>
              </div>
              <div className="text-xs text-gray-600 space-y-1.5 bg-gray-50 rounded-md p-3">
                <p>After checking this section, configure it:</p>
                <p>• <strong>View:</strong> Select "Lot" (not "Summary") — this preserves individual purchase lots with exact cost basis</p>
                <p>• <strong>Fields:</strong> Click "Select All" to include all available data fields</p>
              </div>
            </div>

            {/* Trades */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">Trades</p>
                  <p className="text-xs text-gray-500 mt-0.5">Shows your buy/sell transaction history</p>
                </div>
                <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded">Required</span>
              </div>
              <div className="text-xs text-gray-600 space-y-1.5 bg-gray-50 rounded-md p-3">
                <p>After checking this section, configure it:</p>
                <p>• <strong>Options:</strong> Select "Execution" (not "Closed Lots" or "Wash Sales")</p>
                <p>• <strong>Fields:</strong> Click "Select All" — includes symbol, price, quantity, date, fees, etc.</p>
              </div>
            </div>

            {/* Cash Report */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">Cash Report</p>
                  <p className="text-xs text-gray-500 mt-0.5">Shows your cash balances by currency</p>
                </div>
                <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded">Required</span>
              </div>
              <div className="text-xs text-gray-600 space-y-1.5 bg-gray-50 rounded-md p-3">
                <p>• <strong>Fields:</strong> Click "Select All"</p>
                <p>Without this section, your cash balance will show as $0</p>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-500">
              <strong>Tip:</strong> You can enable additional sections like "Account Information" for extra metadata,
              but the three above are the minimum required for full functionality.
            </p>
          </div>
        </div>
      ),
    },

    // Page 5: Delivery Settings
    {
      title: 'Configure Delivery Settings',
      subtitle: 'Step 3 of 4 (continued)',
      content: (
        <div className="space-y-6">
          <p className="text-gray-600 leading-relaxed">
            Before saving, configure these delivery settings. The Period setting is especially important
            — it controls how much trade history you'll receive.
          </p>

          <div className="border border-gray-200 rounded-lg divide-y divide-gray-100">
            <div className="p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-gray-900">Format</p>
                  <p className="text-xs text-gray-500 mt-0.5">Data format for the API</p>
                </div>
                <span className="font-mono text-sm text-gray-900 bg-gray-50 px-2 py-1 rounded">XML</span>
              </div>
            </div>

            <div className="p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-gray-900">Period</p>
                  <p className="text-xs text-gray-500 mt-0.5">How far back to fetch trades</p>
                </div>
                <span className="font-mono text-sm text-gray-900 bg-gray-50 px-2 py-1 rounded">Last 365 Days</span>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Choose "Last 365 Days" for full trade history (recommended for post-mortems).
                Use "Last 30 Days" or "Last 7 Days" if you only need recent trades.
              </p>
            </div>

            <div className="p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-gray-900">Include Currency Rates</p>
                  <p className="text-xs text-gray-500 mt-0.5">For multi-currency accounts</p>
                </div>
                <span className="font-mono text-sm text-emerald-700 bg-emerald-50 px-2 py-1 rounded">Yes</span>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium text-gray-900">Other settings (leave as default)</p>
            <div className="text-xs text-gray-500 space-y-1">
              <p>• Date Format: yyyyMMdd</p>
              <p>• Time Format: HHmmss</p>
              <p>• Include Canceled Trades: No</p>
              <p>• Include Audit Trail: No</p>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-500">
              <strong>Note:</strong> You can change the Period later and re-sync to fetch more historical trades.
              Each sync only adds new trades — it never deletes existing ones.
            </p>
          </div>
        </div>
      ),
    },

    // Page 6: Save & Get Query ID
    {
      title: 'Save & Get Query ID',
      subtitle: 'Step 4 of 4',
      content: (
        <div className="space-y-6">
          <p className="text-gray-600 leading-relaxed">
            Save your Flex Query and copy the Query ID. You'll need this along with a Token to connect.
          </p>

          <div className="space-y-5">
            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">1</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Click "Continue" at the bottom of the page</p>
                <p className="text-xs text-gray-500">Review your selections on the summary screen</p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">2</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Click "Create" or "Save"</p>
                <p className="text-xs text-gray-500">Your query will be saved and appear in the list</p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">3</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Find and copy your Query ID</p>
                <p className="text-xs text-gray-500 mb-2">
                  In the Flex Queries list, look for a 6-10 digit number next to your query name.
                  This is your Query ID.
                </p>
                <div className="bg-gray-50 rounded-md px-3 py-2">
                  <p className="text-xs text-gray-500 mb-1">Example Query ID:</p>
                  <p className="font-mono text-sm text-gray-900">847291</p>
                </div>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-500">
              <strong>Save this Query ID</strong> — you'll paste it in the connection form.
              Next, we'll get the Token (a secure API key).
            </p>
          </div>
        </div>
      ),
    },

    // Page 7: Get Token
    {
      title: 'Enable Flex Web Service',
      subtitle: 'Step 4 of 4 (continued)',
      content: (
        <div className="space-y-6">
          <p className="text-gray-600 leading-relaxed">
            The Token is a secure API key that authorizes us to fetch your Flex Query data.
            It's separate from your IBKR password and provides read-only access.
          </p>

          <div className="space-y-5">
            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">1</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Find "Flex Web Service" settings</p>
                <p className="text-xs text-gray-500">
                  On the Flex Queries page, look on the right side or top for a link/button labeled
                  "Flex Web Service Configuration" or a gear icon.
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">2</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Enable the Flex Web Service</p>
                <p className="text-xs text-gray-500">
                  Check the box next to "Flex Web Service Status" to enable it, then click "Save".
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">3</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Copy the "Current Token"</p>
                <p className="text-xs text-gray-500 mb-2">
                  After enabling, a 24-digit token will be displayed. Copy it carefully.
                </p>
                <div className="bg-gray-50 rounded-md px-3 py-2">
                  <p className="text-xs text-gray-500 mb-1">Example Token:</p>
                  <p className="font-mono text-sm text-gray-900">482957104820174928501748</p>
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">4</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900 mb-1">Optional: Extend token expiration</p>
                <p className="text-xs text-gray-500">
                  By default, tokens expire in 6 hours. Scroll down to "Token Generation",
                  set expiration to "1 Year", and click "Generate New Token" to get a long-lived token.
                </p>
              </div>
            </div>
          </div>

          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
            <p className="text-sm font-medium text-gray-900 mb-2">You now have both credentials:</p>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Query ID</span>
                <span className="text-gray-900">6-10 digits</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Current Token</span>
                <span className="text-gray-900">24 digits</span>
              </div>
            </div>
          </div>
        </div>
      ),
    },

    // Page 8: Connect & Troubleshooting
    {
      title: 'Connect Your Account',
      subtitle: 'Final step',
      content: (
        <div className="space-y-6">
          <p className="text-gray-600 leading-relaxed">
            Enter your credentials in the connection form. Your portfolio will be created automatically
            with all positions and trades imported.
          </p>

          <div className="border border-gray-200 rounded-lg divide-y divide-gray-100">
            <div className="p-4">
              <p className="text-xs text-gray-500 mb-1">Current Token</p>
              <p className="text-sm text-gray-900">Paste your 24-digit token</p>
            </div>
            <div className="p-4">
              <p className="text-xs text-gray-500 mb-1">Flex Query ID</p>
              <p className="text-sm text-gray-900">Paste your 6-10 digit Query ID</p>
            </div>
            <div className="p-4">
              <p className="text-xs text-gray-500 mb-1">Connection Name</p>
              <p className="text-sm text-gray-900">A friendly name like "My IBKR Account" or "IRA"</p>
            </div>
          </div>

          <div>
            <p className="text-sm font-medium text-gray-900 mb-3">What happens after connecting</p>
            <ul className="space-y-2 text-sm text-gray-600">
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0" />
                <span>We validate your credentials with IBKR (2-3 seconds)</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0" />
                <span>Your positions and trades are fetched (3-5 seconds)</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0" />
                <span>A new portfolio is created with all your holdings</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full mt-1.5 flex-shrink-0" />
                <span>Automatic sync runs twice daily (12 PM & 5:30 PM ET)</span>
              </li>
            </ul>
          </div>

          <div>
            <p className="text-sm font-medium text-gray-900 mb-3">Troubleshooting</p>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-gray-900">"Invalid credentials"</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Double-check both numbers are copied correctly with no extra spaces.
                  Ensure the token hasn't expired (default is 6 hours).
                </p>
              </div>
              <div>
                <p className="text-gray-900">"No positions found"</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Make sure "Open Positions" section is enabled in your Flex Query.
                  Also verify you have actual holdings in your IBKR account.
                </p>
              </div>
              <div>
                <p className="text-gray-900">"Missing trades" or empty transaction history</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Edit your Flex Query in IBKR, change Period to "Last 365 Days", save it,
                  then click "Sync IBKR" in your portfolio. Old trades are preserved.
                </p>
              </div>
              <div>
                <p className="text-gray-900">"Connection timeout"</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  IBKR's servers can be slow. Wait 30 seconds and try again.
                  If the issue persists, check IBKR's status page.
                </p>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-500">
              <strong>After setup:</strong> You can connect multiple IBKR accounts — each creates a separate portfolio.
              Use the "Sync IBKR" button anytime to manually refresh. Disconnect from portfolio settings if needed.
            </p>
          </div>
        </div>
      ),
    },
  ];

  const handleNext = () => {
    if (currentPage < pages.length - 1) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handlePrev = () => {
    if (currentPage > 0) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleClose = () => {
    setCurrentPage(0);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start p-6 pb-0">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {pages[currentPage].title}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {pages[currentPage].subtitle}
            </p>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 p-1 -mr-1 -mt-1 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {pages[currentPage].content}
        </div>

        {/* Footer */}
        <div className="p-6 pt-4 border-t border-gray-100">
          <div className="flex justify-between items-center">
            {/* Progress */}
            <div className="flex gap-1.5">
              {pages.map((_, index) => (
                <button
                  key={index}
                  onClick={() => setCurrentPage(index)}
                  className={`h-1 rounded-full transition-all ${
                    index === currentPage
                      ? 'bg-gray-900 w-6'
                      : 'bg-gray-200 w-1 hover:bg-gray-300'
                  }`}
                />
              ))}
            </div>

            {/* Navigation */}
            <div className="flex gap-2">
              {currentPage > 0 && (
                <button
                  onClick={handlePrev}
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1 transition-colors"
                >
                  <ChevronLeft size={16} />
                  Back
                </button>
              )}
              <button
                onClick={currentPage === pages.length - 1 ? handleClose : handleNext}
                className="px-4 py-1.5 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 flex items-center gap-1 transition-colors"
              >
                {currentPage === pages.length - 1 ? (
                  'Done'
                ) : (
                  <>
                    Next
                    <ChevronRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
