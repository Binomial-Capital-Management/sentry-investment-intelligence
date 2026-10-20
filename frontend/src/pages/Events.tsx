/**
 * Events Page
 *
 * Market news timeline and economic calendar with TradingView integration.
 */

import React from 'react';
import TradingViewTimeline from '../components/Events/TradingViewTimeline';
import TradingViewEconomicCalendar from '../components/Events/TradingViewEconomicCalendar';

export const Events: React.FC = () => {
  return (
    <div style={{
      height: '100vh',
      background: 'var(--bg-base)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header Section */}
      <div style={{
        padding: '16px 40px',
        borderBottom: '1px solid var(--border-light)',
        background: 'linear-gradient(135deg, #FFFFFF 0%, #F9FAFB 100%)',
      }}>
        <div style={{ maxWidth: '1600px', margin: '0 auto' }}>
          <h1 style={{
            fontSize: '24px',
            fontWeight: '600',
            color: '#1A1A1A',
            margin: 0,
            marginBottom: '4px',
            fontFamily: 'var(--font-display)',
            letterSpacing: '-0.5px',
          }}>
            Market Events & News
          </h1>
          <p style={{
            fontSize: '13px',
            color: '#605E5C',
            lineHeight: '1.5',
            margin: 0,
          }}>
            Real-time market news and upcoming economic events powered by TradingView
          </p>
        </div>
      </div>

      {/* Content Area - Two Column Layout */}
      <div style={{
        flex: 1,
        padding: '24px',
        overflow: 'auto',
      }}>
        <div style={{
          maxWidth: '1600px',
          margin: '0 auto',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))',
          gap: '24px',
          height: '100%',
        }}>
          {/* News Timeline */}
          <div style={{
            background: 'var(--bg-card)',
            borderRadius: '12px',
            border: '1px solid var(--border)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}>
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid var(--border-light)',
              background: '#FAFAFA',
            }}>
              <h2 style={{
                fontSize: '18px',
                fontWeight: '600',
                color: '#1A1A1A',
                margin: 0,
              }}>
                Market News
              </h2>
              <p style={{
                fontSize: '13px',
                color: '#605E5C',
                margin: '4px 0 0 0',
              }}>
                Latest market stories and updates
              </p>
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <TradingViewTimeline
                displayMode="regular"
                feedMode="all_symbols"
                colorTheme="light"
                isTransparent={false}
                locale="en"
                width="100%"
                height="100%"
              />
            </div>
          </div>

          {/* Economic Calendar */}
          <div style={{
            background: 'var(--bg-card)',
            borderRadius: '12px',
            border: '1px solid var(--border)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}>
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid var(--border-light)',
              background: '#FAFAFA',
            }}>
              <h2 style={{
                fontSize: '18px',
                fontWeight: '600',
                color: '#1A1A1A',
                margin: 0,
              }}>
                Economic Calendar
              </h2>
              <p style={{
                fontSize: '13px',
                color: '#605E5C',
                margin: '4px 0 0 0',
              }}>
                Upcoming economic events and releases
              </p>
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <TradingViewEconomicCalendar
                colorTheme="light"
                isTransparent={false}
                locale="en"
                countryFilter="ar,au,br,ca,cn,fr,de,in,id,it,jp,kr,mx,ru,sa,za,tr,gb,us,eu"
                importanceFilter="-1,0,1"
                width="100%"
                height="100%"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
