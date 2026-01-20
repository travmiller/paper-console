import { useState, useEffect } from 'react';

// Fallback module types to prevent app crash if API fails
const FALLBACK_MODULE_TYPES = [
  { id: 'news', label: 'News API', offline: false, icon: 'newspaper' },
  { id: 'weather', label: 'Weather', offline: false, icon: 'cloud-sun' },
];

let cachedTypes = null;
let loadPromise = null;

export function useModuleTypes() {
  const [moduleTypes, setModuleTypes] = useState(cachedTypes || []);
  const [loading, setLoading] = useState(!cachedTypes);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (cachedTypes) {
      setModuleTypes(cachedTypes);
      setLoading(false);
      return;
    }

    if (!loadPromise) {
      loadPromise = fetch('/api/module-types')
        .then(res => {
          if (!res.ok) throw new Error('Failed to load module types');
          return res.json();
        })
        .then(data => {
          cachedTypes = data.moduleTypes || [];
          return cachedTypes;
        })
        .catch(err => {
          console.error('Error loading module types:', err);
          cachedTypes = FALLBACK_MODULE_TYPES; // Use fallback on error
          return cachedTypes;
        });
    }

    loadPromise.then(types => {
      setModuleTypes(types);
      setLoading(false);
    });
  }, []);

  return { moduleTypes, loading, error };
}
