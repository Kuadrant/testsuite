"""UI test timeout constants"""

# Playwright timeout constants (in milliseconds)
# OpenShift console loading times vary based on cluster load, network conditions, and CI environments
# These timeouts allow sufficient time for operations to complete without timing out prematurely
# Playwright only waits up to the timeout if the operation doesn't complete earlier

UI_PAGE_LOAD_TIMEOUT = 60000  # 60 seconds - for page navigation, editor loads, major UI elements
UI_NAVIGATION_TIMEOUT = 30000  # 30 seconds - for URL changes and navigation state transitions
UI_ELEMENT_TIMEOUT = 10000  # 10 seconds - for quick element interactions (buttons, form fields)
UI_SESSION_INIT_TIMEOUT = 2000  # 2 seconds - for session initialization and quick waits
