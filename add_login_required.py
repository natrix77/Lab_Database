import re

def add_login_required_decorator():
    # Read the file
    with open('simple_app.pyw', 'r', encoding='utf-8') as file:
        content = file.read()

    # Define the pattern to find route decorators
    pattern = r'(@app\.route\([^\)]*\))\n'
    
    # Define the routes to exclude
    exclude_routes = [
        '@app.route(\'/login\'',
        '@app.route(\'/logout\'',
        '@app.route(\'/\')'  # We already manually modified this one
    ]
    
    # Define the replacement function
    def add_decorator(match):
        route_decorator = match.group(1)
        
        # Check if this is a route we should exclude
        for exclude_route in exclude_routes:
            if exclude_route in route_decorator:
                return route_decorator + '\n'
        
        # If not excluded, add the login_required decorator
        return route_decorator + '\n@login_required\n'
    
    # Apply the replacements
    modified_content = re.sub(pattern, add_decorator, content)
    
    # Write the result back to the file
    with open('simple_app.pyw', 'w', encoding='utf-8') as file:
        file.write(modified_content)
    
    print("Login_required decorator added to all routes.")

if __name__ == '__main__':
    add_login_required_decorator() 