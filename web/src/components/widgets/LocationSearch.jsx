import React, { useState } from 'react';
import { commonClasses } from '../../design-tokens';

const LocationSearch = ({ value = {}, onChange }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async (term) => {
    setSearchTerm(term);
    if (term.length < 2) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const response = await fetch(`/api/location/search?q=${encodeURIComponent(term)}&limit=10`);
      const data = await response.json();
      if (data.results) {
        setSearchResults(data.results);
      } else {
        setSearchResults([]);
      }
    } catch (err) {
      console.error('Error fetching locations:', err);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const selectLocation = (loc) => {
    const newLocation = {
        city_name: loc.name,
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
    <div className="space-y-3">
      <div className="relative">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Type zip code or city name..."
          className={commonClasses.input}
          autoComplete="off"
        />
        {isSearching && (
             <div className="absolute right-3 top-2.5 text-gray-400 text-xs">Searching...</div>
        )}
        
        {searchResults.length > 0 && (
          <ul className="absolute w-full z-10 max-h-[200px] overflow-y-auto bg-white border-2 border-gray-300 border-t-0 rounded-b-lg shadow-lg list-none p-0 m-0">
            {searchResults.map((result) => (
              <li
                key={result.id}
                onClick={() => selectLocation(result)}
                className="p-3 cursor-pointer border-b-2 border-gray-200 last:border-0 hover:bg-white transition-colors hover:bg-gray-50 bg-white"
              >
                <strong>{result.name}</strong>
                <span className="text-gray-500 text-xs ml-2">
                  {result.state} {result.zipcode ? `(${result.zipcode})` : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {hasLocation ? (
        <div className={`${commonClasses.cardNested} space-y-2`}>
          <div className="flex justify-between">
            <span className={commonClasses.textSubtle}>City</span>
            <span className="text-sm font-medium">{value.city_name}</span>
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
