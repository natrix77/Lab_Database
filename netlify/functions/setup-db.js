const fs = require('fs');
const path = require('path');

exports.handler = async function(event, context) {
  // Create the db directory if it doesn't exist
  const dbDir = path.join(__dirname, 'db');
  if (!fs.existsSync(dbDir)) {
    try {
      fs.mkdirSync(dbDir, { recursive: true });
      console.log('Created database directory:', dbDir);
    } catch (err) {
      console.error('Error creating database directory:', err);
      return {
        statusCode: 500,
        body: JSON.stringify({ error: 'Failed to create database directory' })
      };
    }
  }
  
  return {
    statusCode: 200,
    body: JSON.stringify({ message: 'Database directory setup complete' })
  };
}; 