// MongoDB initialization script
db = db.getSiblingDB('admin');
db.auth('rsstag_admin', 'secure_password');

// Create user in the admin database first
db.createUser({
  user: 'rsstag_user',
  pwd: 'rsstag_password',
  roles: [
    { role: 'readWrite', db: 'rss' }
  ]
});

// Also create the same user in the rss database
db = db.getSiblingDB('rss');
db.createUser({
  user: 'rsstag_user',
  pwd: 'rsstag_password',
  roles: [
    { role: 'readWrite', db: 'rss' }
  ]
});