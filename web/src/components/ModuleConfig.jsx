import React from 'react';
import SchemaForm from './SchemaForm';
import JsonTextarea from './JsonTextarea';
import { commonClasses } from '../design-tokens';

const ModuleConfig = ({ module, updateConfig }) => {
  const config = module.config || {};
  
  // 1. Dynamic Schema-Driven Configuration
  if (module.configSchema) {
      const handleSchemaChange = (newConfig) => {
          // Compare new config with old to find changes
          Object.keys(newConfig).forEach(key => {
              if (newConfig[key] !== config[key]) {
                  updateConfig(key, newConfig[key]);
              }
          });
      };
      
      return (
          <SchemaForm 
              schema={module.configSchema}
              uiSchema={module.uiSchema}
              formData={config}
              onChange={handleSchemaChange}
          />
      );
  }

  // 2. Fallback for generic modules without schema
  return (
    <div className="space-y-3">
        <p className={`${commonClasses.textSubtle} mb-2`}>
            This module does not have a configuration schema. You can edit the raw JSON configuration below.
        </p>
        <JsonTextarea 
            config={config} 
            updateConfig={(key, val) => updateConfig(key, val)} 
        />
    </div>
  );
};

export default ModuleConfig;
