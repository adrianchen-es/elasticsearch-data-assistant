// frontend/src/utils/mobileUtils.js
import { useState, useEffect } from 'react';

/**
 * Custom hook to detect mobile devices and screen sizes
 */
export const useMobileDetection = () => {
  const [isMobile, setIsMobile] = useState(false);
  const [isTablet, setIsTablet] = useState(false);
  const [screenSize, setScreenSize] = useState('desktop');

  useEffect(() => {
    const checkDevice = () => {
      const width = window.innerWidth;
      const isMobileDevice = width < 768; // Tailwind's md breakpoint
      const isTabletDevice = width >= 768 && width < 1024; // Between md and lg
      
      setIsMobile(isMobileDevice);
      setIsTablet(isTabletDevice);
      
      if (isMobileDevice) {
        setScreenSize('mobile');
      } else if (isTabletDevice) {
        setScreenSize('tablet');
      } else {
        setScreenSize('desktop');
      }
    };

    // Check on mount
    checkDevice();

    // Add event listener for resize
    window.addEventListener('resize', checkDevice);

    // Cleanup
    return () => window.removeEventListener('resize', checkDevice);
  }, []);

  return {
    isMobile,
    isTablet,
    screenSize,
    isDesktop: screenSize === 'desktop'
  };
};

/**
 * Utility function to get responsive classes based on screen size
 */
export const getResponsiveClasses = (mobileClass, tabletClass = '', desktopClass = '') => {
  return `${mobileClass} ${tabletClass ? `sm:${tabletClass}` : ''} ${desktopClass ? `lg:${desktopClass}` : ''}`.trim();
};

/**
 * Touch-friendly sizing for interactive elements
 */
export const getTouchFriendlySize = (element = 'button') => {
  const sizes = {
    button: 'min-h-[44px] min-w-[44px]', // Apple's recommended minimum touch target
    input: 'min-h-[44px]',
    select: 'min-h-[44px]',
    checkbox: 'w-5 h-5 sm:w-4 sm:h-4',
    icon: 'w-5 h-5 sm:w-4 sm:h-4'
  };
  
  return sizes[element] || sizes.button;
};

/**
 * Mobile-specific text sizing
 */
export const getMobileTextSize = (baseSize = 'text-sm') => {
  const mobileSizes = {
    'text-xs': 'text-sm sm:text-xs',
    'text-sm': 'text-base sm:text-sm', 
    'text-base': 'text-lg sm:text-base',
    'text-lg': 'text-xl sm:text-lg',
    'text-xl': 'text-2xl sm:text-xl'
  };
  
  return mobileSizes[baseSize] || baseSize;
};

/**
 * Mobile-friendly spacing
 */
export const getMobileSpacing = (spacing = 'p-4') => {
  const mobileSpacing = {
    'p-2': 'p-3 sm:p-2',
    'p-3': 'p-4 sm:p-3', 
    'p-4': 'p-3 sm:p-4',
    'p-6': 'p-4 sm:p-6',
    'px-2': 'px-3 sm:px-2',
    'px-3': 'px-4 sm:px-3',
    'px-4': 'px-3 sm:px-4',
    'py-2': 'py-3 sm:py-2',
    'py-3': 'py-4 sm:py-3'
  };
  
  return mobileSpacing[spacing] || spacing;
};

/**
 * Responsive container widths
 */
export const getResponsiveContainer = (size = 'default') => {
  const containers = {
    'default': 'w-full max-w-full sm:max-w-3xl',
    'narrow': 'w-full max-w-full sm:max-w-lg',
    'wide': 'w-full max-w-full sm:max-w-5xl',
    'full': 'w-full'
  };
  
  return containers[size] || containers.default;
};

const mobileUtils = {
  useMobileDetection,
  getResponsiveClasses,
  getTouchFriendlySize,
  getMobileTextSize,
  getMobileSpacing,
  getResponsiveContainer
};

export default mobileUtils;
