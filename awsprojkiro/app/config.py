import os

class Config:
    """Base configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dominoes-secret-key-change-in-production'
    DEBUG = False
    TESTING = False
    
    # Database configuration (for future RDS integration)
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # AWS specific configurations
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Application specific settings
    MAX_GAMES_IN_MEMORY = int(os.environ.get('MAX_GAMES_IN_MEMORY', '1000'))
    
    # Cost monitoring settings
    PROJECT_NAME = os.environ.get('PROJECT_NAME', 'dominoes-app')
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
    COST_MONITORING_ENABLED = os.environ.get('COST_MONITORING_ENABLED', 'true').lower() == 'true'
    FREE_TIER_WARNING_THRESHOLD = int(os.environ.get('FREE_TIER_WARNING_THRESHOLD', '80'))

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SECRET_KEY = 'dev-secret-key-not-for-production'

class ProductionConfig(Config):
    """Production configuration for AWS deployment"""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    @classmethod
    def validate(cls):
        """Validate production configuration at runtime"""
        if not cls.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set in production")

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}