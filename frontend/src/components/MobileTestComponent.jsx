import React from 'react';
import { useMobileDetection, getTouchFriendlySize, getMobileTextSize } from '../utils/mobileUtils';
import '../styles/responsive.css';

const MobileTestComponent = () => {
  const { isMobile, isTablet, screenSize } = useMobileDetection();

  return (
    <div className="p-4 space-y-4">
      <h2 className={`font-bold ${getMobileTextSize('text-xl')}`}>
        Mobile Responsiveness Test
      </h2>
      
      <div className="bg-blue-50 p-3 rounded-lg">
        <h3 className="font-semibold mb-2">Device Detection:</h3>
        <p>Screen Size: {screenSize}</p>
        <p>Is Mobile: {isMobile ? 'Yes' : 'No'}</p>
        <p>Is Tablet: {isTablet ? 'Yes' : 'No'}</p>
        <p>Window Width: {window.innerWidth}px</p>
      </div>

      <div className="space-y-2">
        <h3 className="font-semibold">Touch-Friendly Buttons:</h3>
        <div className="flex flex-col sm:flex-row gap-2">
          <button className={`${getTouchFriendlySize('button')} bg-blue-500 text-white rounded-lg px-4 touch-button`}>
            Mobile Button
          </button>
          <button className={`${getTouchFriendlySize('button')} bg-green-500 text-white rounded-lg px-4 touch-button`}>
            Another Button
          </button>
        </div>
      </div>

      <div className="mobile-grid">
        <div className="bg-gray-100 p-3 rounded">Grid Item 1</div>
        <div className="bg-gray-100 p-3 rounded">Grid Item 2</div>
        <div className="bg-gray-100 p-3 rounded">Grid Item 3</div>
      </div>

      <div className="space-y-2">
        <h3 className="font-semibold">Responsive Text Sizes:</h3>
        <p className={getMobileTextSize('text-xs')}>Extra small text (responsive)</p>
        <p className={getMobileTextSize('text-sm')}>Small text (responsive)</p>
        <p className={getMobileTextSize('text-base')}>Base text (responsive)</p>
        <p className={getMobileTextSize('text-lg')}>Large text (responsive)</p>
      </div>

      <div className="mobile-scroll bg-gray-50 p-3 rounded max-h-32 overflow-y-auto">
        <h3 className="font-semibold mb-2">Mobile Optimized Scroll:</h3>
        {Array.from({ length: 20 }, (_, i) => (
          <p key={i} className="py-1">Scrollable content item {i + 1}</p>
        ))}
      </div>

      <div className="space-y-2">
        <h3 className="font-semibold">Form Elements:</h3>
        <input 
          type="text" 
          placeholder="Mobile-optimized input"
          className="mobile-input w-full"
        />
        <textarea 
          placeholder="Mobile-optimized textarea"
          className="mobile-input w-full"
          rows="3"
        />
      </div>
    </div>
  );
};

export default MobileTestComponent;
