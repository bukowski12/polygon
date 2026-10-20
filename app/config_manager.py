"""
Secure configuration manager with validation and error handling.
"""
import os
import configparser
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from logger_config import logger


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""
    pass


@dataclass(frozen=True)
class SiteConfig:
    """SITE-CONFIG-01: identity of the site from [SITE] - window title,
    protocol header/footer, logbook header, e-mail report. The defaults are
    neutral (dict configs of tests and helper code paths); a real config
    file must have [SITE] - ConfigManager requires it."""
    name: str = "Polygon"
    organization: str = ""   # may span several lines (configparser continuation)
    address: str = ""
    place: str = ""
    logo: Optional[str] = None   # local image file; None = the bundled logo

    @property
    def organization_lines(self) -> Tuple[str, ...]:
        return tuple(line.strip() for line in self.organization.splitlines() if line.strip())


def site_from_config(config) -> SiteConfig:
    """[SITE] of a loaded config as SiteConfig; neutral values for whatever
    is missing (ConfigManager has already rejected a file without it)."""
    section = config.get('SITE') or {}

    def text(key):
        value = section.get(key)
        return "" if value is None or isinstance(value, bool) else str(value).strip()

    return SiteConfig(text('name') or SiteConfig.name, text('organization'), text('address'), text('place'),
                      text('logo') or None)


class ConfigManager:
    """Secure configuration manager with validation."""
    
    def __init__(self, config_file: str):
        self.config_file = config_file
        self._config = {}
        self._required_sections = {
            'MYSQL': ['host', 'user', 'password', 'database'],
            'LDAP': ['host', 'username', 'password', 'base', 'group'],
            'QUIDO': ['din', 'dout'],
            'CAMERA': ['width', 'height'],  # disable is optional
            'AUDIO': ['file'],
            'SITE': ['name', 'organization', 'place'],  # SITE-CONFIG-01; address and logo are optional
        }
        
    def load_config(self) -> Dict[str, Any]:
        """Load and validate configuration from file."""
        if not os.path.exists(self.config_file):
            raise ConfigurationError(f"Configuration file not found: {self.config_file}")
            
        try:
            config = configparser.ConfigParser()
            config.optionxform = str  # Preserve case sensitivity
            config.read(self.config_file)
            
            # Convert to dictionary with type conversion
            for section_name in config.sections():
                self._config[section_name] = {}
                for option in config.options(section_name):
                    value = config.get(section_name, option)
                    # Convert boolean strings
                    if value.lower() in ('true', 'false'):
                        self._config[section_name][option] = config.getboolean(section_name, option)
                    else:
                        self._config[section_name][option] = value
                        
            self._validate_config()
            logger.info("Configuration loaded successfully")
            return self._config
            
        except configparser.Error as e:
            logger.error(f"Configuration parsing error: {e}")
            raise ConfigurationError(f"Failed to parse configuration: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _validate_config(self) -> None:
        """Validate required configuration sections and keys."""
        for section, required_keys in self._required_sections.items():
            if section not in self._config:
                raise ConfigurationError(f"Missing required section: {section}")

            for key in required_keys:
                if key not in self._config[section]:
                    raise ConfigurationError(f"Missing required key '{key}' in section '{section}'")

                # Check for empty values (but allow boolean False)
                value = self._config[section][key]
                if value is None or (isinstance(value, str) and not value.strip()):
                    raise ConfigurationError(f"Empty value for required key '{key}' in section '{section}'")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Safely get configuration value."""
        try:
            return self._config[section][key]
        except KeyError:
            if default is not None:
                return default
            raise ConfigurationError(f"Configuration key '{section}.{key}' not found")
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section."""
        if section not in self._config:
            raise ConfigurationError(f"Configuration section '{section}' not found")
        return self._config[section].copy()  # Return copy to prevent modification
