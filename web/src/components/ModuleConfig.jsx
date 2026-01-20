import React from 'react';
import SchemaForm from './SchemaForm';
import JsonTextarea from './JsonTextarea';
import { commonClasses } from '../design-tokens';
import { useModuleTypes } from '../hooks/useModuleTypes';

const ModuleConfig = ({ module, updateConfig }) => {
  const { moduleTypes, loading } = useModuleTypes();
  const config = module.config || {};
  
  const typeDef = moduleTypes.find(t => t.id === module.type);
  const configSchema = typeDef?.configSchema;
  const uiSchema = typeDef?.uiSchema;
  
  // 1. Dynamic Schema-Driven Configuration
  if (configSchema) {
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
              schema={configSchema}
              uiSchema={uiSchema}
              formData={config}
              onChange={handleSchemaChange}
          />
      );
  }

  if (loading) {
      return <div className="p-4 text-center text-gray-500 italic">Loading configuration schema...</div>;
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
