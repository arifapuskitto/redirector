import streamlit as st
import webbrowser
import time
import validators
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile

def read_redirect_urls():
    """Read redirect URLs from the redirect.txt file"""
    with open('redirect.txt', 'r') as file:
        return file.readlines()

def format_url(template_url, target_url):
    """Format the redirect URL by replacing {url} placeholder with target URL"""
    return template_url.strip().replace('{url}', target_url)

def is_valid_url(url):
    """Check if the URL is valid"""
    try:
        # Add http:// if not present (validators requires protocol)
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        return validators.url(url)
    except:
        return False

def setup_headless_driver():
    """Setup and return a headless Chrome browser"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Updated headless argument
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    
    # Create a temporary directory for WebDriver
    temp_dir = tempfile.mkdtemp()
    os.environ['WDM_LOCAL'] = '1'
    os.environ['WDM_PATH'] = temp_dir
    
    try:
        service = Service()
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        st.error(f"Failed to initialize Chrome driver: {str(e)}")
        st.info("Please make sure Google Chrome is installed on your system.")
        return None

def extract_final_url(driver):
    """Extract the final URL from the redirect page and follow it"""
    try:
        # Wait for and find the first link in the page
        link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )
        destination_url = link.get_attribute("href")
        
        # Navigate to the destination URL
        driver.get(destination_url)
        
        # Wait for the page to load and return the final URL
        WebDriverWait(driver, 10).until(
            lambda driver: driver.current_url != destination_url
        )
        return {
            "destination_url": destination_url,
            "final_url": driver.current_url
        }
    except Exception as e:
        st.warning(f"Could not extract final URL: {str(e)}")
        return {
            "destination_url": driver.current_url,
            "final_url": driver.current_url
        }

def follow_redirect_headless(url, progress_callback=None):
    """Follow redirect using headless browser and return all URLs in the chain"""
    driver = setup_headless_driver()
    if not driver:
        return {
            "redirect_url": url,
            "destination_url": url,
            "final_url": url
        }
    
    try:
        driver.get(url)
        redirect_url = driver.current_url
        urls = extract_final_url(driver)
        
        if progress_callback:
            progress_callback()
            
        return {
            "redirect_url": redirect_url,
            "destination_url": urls["destination_url"],
            "final_url": urls["final_url"]
        }
    except Exception as e:
        st.warning(f"Failed to follow redirect for {url}: {str(e)}")
        return {
            "redirect_url": url,
            "destination_url": url,
            "final_url": url
        }
    finally:
        try:
            driver.quit()
        except:
            pass

def main():
    st.title("Bulk URL Opener")
    st.write("Enter a URL to open multiple redirect links")
    
    # Input field for the URL
    target_url = st.text_input("Enter your URL (without https://)")
    
    # Add URL count selector
    total_urls = len(read_redirect_urls())
    num_urls = st.slider("Number of URLs to open", 1, total_urls, total_urls)
    
    # Add delay customization
    delay = st.slider("Delay between opening tabs (seconds)", 0.1, 2.0, 0.1, 0.1)
    
    # Add method selector
    method = st.radio(
        "Choose redirect method",
        ["Browser Tabs", "Headless Browser (Server-side)"]
    )
    
    # Create placeholder for the process button and status
    button_placeholder = st.empty()
    status_container = st.container()
    
    if button_placeholder.button("Process URLs", disabled=not target_url):
        # Clear the button while processing
        button_placeholder.empty()
        
        # Remove https:// if user accidentally included it
        target_url = target_url.replace('https://', '').replace('http://', '')
        
        # Validate URL
        if not is_valid_url(target_url):
            st.error("Please enter a valid URL!")
            return
        
        try:
            with status_container:
                with st.spinner('Processing URLs... Please wait.'):
                    # Read redirect URLs from file
                    redirect_urls = read_redirect_urls()[:num_urls]
                    
                    # Create progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    if method == "Browser Tabs":
                        # Open URLs in browser tabs
                        for i, redirect_url in enumerate(redirect_urls):
                            progress = (i + 1) / len(redirect_urls)
                            progress_bar.progress(progress)
                            status_text.text(f"Opening URL {i + 1} of {len(redirect_urls)}")
                            
                            formatted_url = format_url(redirect_url, target_url)
                            webbrowser.open_new_tab(formatted_url)
                            time.sleep(delay)
                        
                        progress_bar.progress(1.0)
                        status_text.text("Complete!")
                        st.success(f"Successfully opened {len(redirect_urls)} URLs in new tabs!")
                        
                    else:  # Headless Browser method
                        final_urls = []
                        processed_count = 0
                        
                        def update_progress():
                            nonlocal processed_count
                            processed_count += 1
                            progress = processed_count / len(redirect_urls)
                            progress_bar.progress(progress)
                            status_text.text(f"Processing URL {processed_count} of {len(redirect_urls)}")
                        
                        # Process URLs in parallel using ThreadPoolExecutor
                        with ThreadPoolExecutor(max_workers=3) as executor:
                            futures = []
                            for redirect_url in redirect_urls:
                                formatted_url = format_url(redirect_url, target_url)
                                future = executor.submit(
                                    follow_redirect_headless, 
                                    formatted_url, 
                                    update_progress
                                )
                                futures.append(future)
                            
                            # Collect results
                            for future in futures:
                                try:
                                    result = future.result()
                                    final_urls.append(result)
                                except Exception as e:
                                    st.warning(f"Failed to process URL: {str(e)}")
                        
                        # Display results
                        progress_bar.progress(1.0)
                        status_text.text("Complete!")
                        st.success(f"Successfully processed {len(final_urls)} URLs!")
                        
                        # Show final URLs in an expandable section
                        with st.expander("View Final URLs"):
                            for i, result in enumerate(final_urls, 1):
                                st.markdown(f"""
                                **{i}.**
                                - Redirect URL: `{result['redirect_url']}`
                                - Destination URL: `{result['destination_url']}`
                                - Final URL: `{result['final_url']}`
                                """)
                                
                                # Add buttons to open URLs
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    if st.button(f"Open Redirect #{i}"):
                                        webbrowser.open_new_tab(result['redirect_url'])
                                with col2:
                                    if st.button(f"Open Destination #{i}"):
                                        webbrowser.open_new_tab(result['destination_url'])
                                with col3:
                                    if st.button(f"Open Final #{i}"):
                                        webbrowser.open_new_tab(result['final_url'])
                                
                                st.markdown("---")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
        
        finally:
            # Restore the process button after completion or error
            button_placeholder.button("Process URLs", disabled=not target_url)
    
    # Add some helpful instructions
    st.markdown("""
    ### Instructions:
    1. Enter your website URL without 'https://'
    2. Adjust the number of URLs to open (default is all)
    3. Adjust the delay between opening tabs if needed
    4. Choose your preferred method:
        - **Browser Tabs**: Opens URLs in new browser tabs
        - **Headless Browser**: Follows redirects server-side and shows final URLs
    5. Click 'Process URLs' button
    
    **Example:** If your URL is `https://example.com`, just enter `example.com`
    """)

if __name__ == "__main__":
    main() 