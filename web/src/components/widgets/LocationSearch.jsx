import React, { useState, useRef, useEffect } from 'react';
import { commonClasses } from '../../design-tokens';

const LocationSearch = ({ value = {}, onChange, placeholder = 'Type city name (e.g. Boston, London, Tokyo)' }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const containerRef = useRef(null);
  const searchTimerRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setSearchResults([]);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearch = async (term) => {
    setSearchTerm(term);
    
    // Clear any pending search
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current);
    }
    
    if (term.length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    // Debounce the search to respect API rate limits
    // Using 500ms to match system setting behavior
    searchTimerRef.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout
        
        // Use local database logic (use_api=false) and higher limit (20) to match General Settings
        const response = await fetch(`/api/location/search?q=${encodeURIComponent(term)}&limit=20&use_api=false`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        const data = await response.json();
        if (data.results) {
          setSearchResults(data.results);
        } else {
          setSearchResults([]);
        }
      } catch (err) {
        if (err.name === 'AbortError') {
             console.warn('Location search timed out');
        } else {
             console.error('Error fetching locations:', err);
             setSearchResults([]);
        }
      } finally {
        setIsSearching(false);
      }
    }, 500);
  };

  const selectLocation = (loc) => {
    // Smart mapping: Prefer raw city name if available, fallback to display name
    // This prevents "City, State, State" issues in display
    const cityName = loc.city || loc.name;

    const newLocation = {
      city_name: cityName,
      latitude: loc.latitude,
      longitude: loc.longitude,
      timezone: loc.timezone,
      state: loc.state,
      zipcode: loc.zipcode
    };
    onChange(newLocation);
    setSearchTerm('');
    setSearchResults([]);
  };

  const hasLocation = value && value.city_name;

  return (
    <div className="space-y-3" ref={containerRef}>
      <div className="relative">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder={placeholder}
          className={commonClasses.input}
          autoComplete="off"
        />
        {isSearching && (
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin"></div>
          </div>
        )}
        
        {searchResults.length > 0 && (
          <ul className="absolute w-full z-10 max-h-[300px] overflow-y-auto bg-white border-2 border-gray-300 border-t-0 rounded-b-lg shadow-lg list-none p-0 m-0">
            {searchResults.map((result) => (
              <li
                key={result.id}
                onClick={() => selectLocation(result)}
                className="p-3 cursor-pointer border-b-2 border-gray-200 last:border-0 hover:bg-gray-50 transition-colors group"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <strong className="text-black transition-colors">{result.name}</strong>
                      {result.state && (
                        <span className="text-gray-500 text-xs">{result.state}</span>
                      )}
                      {result.zipcode && (
                        <span className="text-gray-500 text-xs">({result.zipcode})</span>
                      )}
                      {result.population && result.population > 0 && (
                        <span className="text-xs text-gray-600">
                          {result.population >= 1000000
                            ? `${(result.population / 1000000).toFixed(1)}M`
                            : result.population >= 1000
                            ? `${(result.population / 1000).toFixed(0)}K`
                            : result.population}
                        </span>
                      )}
                      {result.country_code && result.country_code !== 'US' && (
                        <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded border border-gray-300">
                          {result.country_code}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {hasLocation ? (
        <div className={`${commonClasses.cardNested} space-y-2`}>
          <div className="flex justify-between">
            <span className={commonClasses.textSubtle}>City</span>
            <span className="text-sm font-medium">
              {value.city_name}
              {value.state && `, ${value.state}`}
            </span>
          </div>
          <div className="flex justify-between">
            <span className={commonClasses.textSubtle}>Timezone</span>
            <span className="text-sm">{value.timezone || 'Not set'}</span>
          </div>
          <div className="flex justify-between">
            <span className={commonClasses.textSubtle}>Coordinates</span>
            <span className="text-sm">
              {value.latitude?.toFixed(4)}, {value.longitude?.toFixed(4)}
            </span>
          </div>
        </div>
      ) : (
        <p className={`${commonClasses.textSubtle} mt-1`}>
          Unless set, uses global location.
        </p>
      )}
    </div>
  );
};

export default LocationSearch;
