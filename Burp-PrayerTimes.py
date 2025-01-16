from burp import IBurpExtender, IExtensionStateListener, ITab
from javax.swing import JLabel, JPanel, JComboBox, JButton, JOptionPane, Timer, Box, BoxLayout, ToolTipManager, JCheckBox
from java.awt import Dimension, Frame
from javax.swing.border import EmptyBorder
import pickle
import urllib2
import json
import datetime
import urllib
import logging

class BurpExtender(IBurpExtender, IExtensionStateListener, ITab):
    def registerExtenderCallbacks(self, callbacks):
        self.callbacks = callbacks
        self.helpers = callbacks.getHelpers()
        callbacks.setExtensionName("Prayer Times")

        self.create_ui_components()

        callbacks.customizeUiComponent(self.panel)
        callbacks.addSuiteTab(self)

        ToolTipManager.sharedInstance().setInitialDelay(100)
        ToolTipManager.sharedInstance().setDismissDelay(60000)

        # Initialize variables
        self.prayer_list = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
        self.prayer_times = None
        self.countries_data = None  
        self.next_prayer_time = None
        self.next_prayer = ""
        self.method_id = ""
        self.city = ""
        self.state = ""
        self.country = ""
        self.lat = ""
        self.lon = ""
        self.timer = None
        self.max_retries = 3

        # Default config
        self.default_config = {
            "state": "Jakarta",
            "city": "Jakarta",
            "country": "Indonesia",
            "alert_checkbox": True,
            "latitude":"-7.6131807",
            "longitude":"110.94838342423252",
            "method": "Muslim World League (ID: 3)"
        }
        
        self.load_countries()
        self.load_methods()
        self.restore_config() # Restore country, alert check box

        # Initial prayer times update
        self.update_prayer_times() 

        callbacks.issueAlert("Prayer Times Extension Loaded.")

    def create_ui_components(self):
        """Create and return the UI panel with all necessary components."""
        self.panel = JPanel()
        self.panel.setLayout(BoxLayout(self.panel, BoxLayout.Y_AXIS))
        self.panel.add(Box.createVerticalStrut(20))

        country_label = JLabel("Choose Country:")
        country_label.setBorder(EmptyBorder(0, 10, 0, 0)) 
        self.countryField = JComboBox()
        self.countryField.setMaximumSize(Dimension(200, 30))
        self.countryField.setAlignmentX(JPanel.LEFT_ALIGNMENT)
        self.countryField.addActionListener(self.load_states)

        self.panel.add(country_label)
        self.panel.add(self.countryField)
        self.panel.add(Box.createVerticalStrut(10))

        state_label = JLabel("Choose State/Province:")
        state_label.setBorder(EmptyBorder(0, 10, 0, 0)) 
        self.stateField = JComboBox()
        self.stateField.setMaximumSize(Dimension(200, 30))
        self.stateField.setAlignmentX(JPanel.LEFT_ALIGNMENT)
        self.stateField.addActionListener(self.load_cities)

        self.panel.add(state_label)
        self.panel.add(self.stateField)
        self.panel.add(Box.createVerticalStrut(10))

        city_label = JLabel("Choose City:")
        city_label.setBorder(EmptyBorder(0, 10, 0, 0)) 
        self.cityField = JComboBox()
        self.cityField.setMaximumSize(Dimension(200, 30))
        self.cityField.setAlignmentX(JPanel.LEFT_ALIGNMENT)

        self.panel.add(city_label)
        self.panel.add(self.cityField)
        self.panel.add(Box.createVerticalStrut(10))

        method_label = JLabel("Choose Prayer Calculation Method:")
        method_label.setBorder(EmptyBorder(0, 10, 0, 0))
        self.methodField = JComboBox()
        self.methodField.setMaximumSize(Dimension(200, 30))
        self.methodField.setAlignmentX(JPanel.LEFT_ALIGNMENT)

        self.panel.add(method_label)
        self.panel.add(self.methodField)
        self.panel.add(Box.createVerticalStrut(10))

        self.alertCheckbox = JCheckBox("Enable Prayer Reminder", True)
        self.panel.add(self.alertCheckbox)
        self.panel.add(Box.createVerticalStrut(10))

        self.button = JButton("Save", actionPerformed=self.update_prayer_times)

        self.button.setMaximumSize(Dimension(200, 30))
        self.panel.add(self.button)
        self.panel.add(Box.createVerticalStrut(10))


    def load_countries(self):
        """Loads country data from external API."""
        attempts = 0
        while attempts < self.max_retries:
            try:
                req = urllib2.Request("https://countriesnow.space/api/v0.1/countries/states")
                req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0')
                data = json.load(urllib2.urlopen(req))

                self.countries_data = data['data']
                self.countryField.removeAllItems()
                for country in self.countries_data:
                    self.countryField.addItem(country['name'])
                break
            except Exception as e:
                    attempts += 1
                    if attempts >= self.max_retries:
                        print("Max retries reached. Unable to fetch countries :  {}".format(str(e)))

    def load_methods(self):
        """Loads prayer calculation methods from Aladhan API."""
        attempts = 0
        while attempts < self.max_retries:
            try:
                req = urllib2.Request("https://api.aladhan.com/v1/methods")
                req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0')
                data = json.load(urllib2.urlopen(req))

                methods = data['data']
                self.methodField.removeAllItems()

                sorted_methods = sorted(
                    methods.items(),
                    key=lambda item: item[1].get('id', float('inf')) 
                )

                for method_key, method_info in sorted_methods:
                    if method_key != "CUSTOM":
                        self.methodField.addItem("{} (ID: {})".format(method_info['name'].encode('utf-8'), method_info['id']))
                break
            except Exception as e:
                    attempts += 1
                    if attempts >= self.max_retries:
                        print("Max retries reached. Unable to fetch method :  {}".format(str(e)))

    def load_states(self, event=None):
        """Loads states based on selected country."""
        selected_country = self.countryField.getSelectedItem()

        self.stateField.removeAllItems()
        for country in self.countries_data:
            if country['name'] == selected_country:
                for state in country['states']:
                    self.stateField.addItem(state['name'])
                break
        self.restore_config("state")

    def load_cities(self, event=None):
        """Loads cities based on selected country and state."""
        selected_country = self.countryField.getSelectedItem() or ""
        selected_state = self.stateField.getSelectedItem() or ""

        self.cityField.removeAllItems()
        if selected_state != "":
            attempts = 0
            while attempts < self.max_retries:
                url = "https://countriesnow.space/api/v0.1/countries/state/cities/q?country={}&state={}".format(urllib.quote(selected_country.encode('utf-8')), urllib.quote(selected_state.encode('utf-8')))
                try:
                    req = urllib2.Request(url)
                    req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0')
                    data = json.load(urllib2.urlopen(req))

                    for city in data['data']:
                        self.cityField.addItem(city)
                    break
                except Exception as e:
                    attempts += 1
                    if attempts >= self.max_retries:
                        print("Max retries reached. Unable to fetch cities :  {} - {}".format(url, str(e)))
        
        self.restore_config("city")
        
    def save_config(self, e=None):
        selected_citytate = self.cityField.getSelectedItem() or ""
        selected_state =  self.stateField.getSelectedItem() or ""
        selected_country =  self.countryField.getSelectedItem() or ""
        selected_method =  self.methodField.getSelectedItem() or ""
        config = {
            'city': selected_citytate.encode('utf-8'),
            'state': selected_state.encode('utf-8'),
            'country': selected_country.encode('utf-8'),
            'method': selected_method.encode('utf-8'),
            'latitude': self.lat,
            'longitude': self.lon,
            'alert_checkbox': self.alertCheckbox.isSelected()
            }
        self.callbacks.saveExtensionSetting("config", pickle.dumps(config))

    def restore_config(self, item="default"):
        storedConfig = self.callbacks.loadExtensionSetting("config")
        if storedConfig is not None:
            try:
                config = pickle.loads(storedConfig)
                if item == "state":
                    self.stateField.setSelectedItem(config.get('state').decode('utf-8'))
                elif item == "city":
                    self.cityField.setSelectedItem(config.get('city').decode('utf-8'))
                else:
                    self.countryField.setSelectedItem(config.get('country').decode('utf-8'))
                    self.alertCheckbox.setSelected(config.get('alert_checkbox'))
                    selected_method = config.get('method')
                    self.methodField.setSelectedItem(selected_method.decode('utf-8'))
                    self.lat = config.get('latitude')
                    self.lon = config.get('longitude')
            except Exception as e:
                print("Failed to restore config: {}".format(str(e)))
        else:
            if item == "state":
                self.stateField.setSelectedItem(self.default_config["state"].decode('utf-8'))
            elif item == "city":
                self.cityField.setSelectedItem(self.default_config["city"].decode('utf-8'))
            else:
                self.countryField.setSelectedItem(self.default_config["country"].decode('utf-8'))
                self.alertCheckbox.setSelected(self.default_config["alert_checkbox"])
                selected_method = self.default_config["method"]
                self.methodField.setSelectedItem(selected_method.decode('utf-8'))
                self.lat = self.default_config["latitude"]
                self.lon = self.default_config["longitude"]


   
    def update_prayer_times(self, event=None):
        """Fetches and updates the prayer times based on location."""
        self.city = self.cityField.getSelectedItem() or ""
        self.state = self.stateField.getSelectedItem() or ""
        self.country = self.countryField.getSelectedItem() or ""
        self.method_id = int(self.methodField.getSelectedItem().split("ID: ")[1].strip(")"))

        updated = False 

        if event != None :
            self.save_config() 
            self.lat, self.lon = self.get_lat_lon()
            self.prayer_times = None

        today = datetime.datetime.now().date()
        today_formatted_date = today.strftime("%d-%m-%Y")
        current_time = datetime.datetime.now().strftime("%H:%M")
        
        attempts = 0
        while attempts < self.max_retries:
            try:
                if self.prayer_times is None:
                    # Fetch today prayer times from API
                    today_url = "https://api.aladhan.com/v1/timings/{}?latitude={}&longitude={}&method={}".format(today_formatted_date, self.lat, self.lon, self.method_id)
            
                    today_req = urllib2.Request(today_url)
                    today_req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0')

                    today_data = json.load(urllib2.urlopen(today_req)  )
                    self.prayer_times = today_data['data']['timings']
                    updated = True

                self.next_prayer, next_time = self.find_next_prayer(self.prayer_times, current_time)
                # Set the next prayer and time
                if self.next_prayer == 'Fajr (Tomorrow)':
                    tomorrow = today + datetime.timedelta(days=1)
                    tommorow_formatted_date = tomorrow.strftime("%d-%m-%Y")

                    # Fetch tommorow prayer times from API
                    tommorow_url = "https://api.aladhan.com/v1/timings/{}?latitude={}&longitude={}&method={}".format(tommorow_formatted_date, self.lat, self.lon, self.method_id)
            
                    tommorow_req = urllib2.Request(tommorow_url)
                    tommorow_req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0')

                    tommorow_data = json.load(urllib2.urlopen(tommorow_req)  )

                    self.prayer_times = tommorow_data['data']['timings']
                    self.next_prayer_time = datetime.datetime.combine(tomorrow, datetime.datetime.strptime(next_time, "%H:%M").time())
                    updated = True
                else:
                    self.next_prayer_time = datetime.datetime.combine(today, datetime.datetime.strptime(next_time, "%H:%M").time())
                break
            except Exception as e:
                attempts += 1
                if attempts >= self.max_retries:
                    print("Max retries reached. Unable to fetch prayer times : {}".format(str(e)))

        if updated == True:
            print("Prayer times updated ({}, {}, {}): {}".format(self.city.encode('utf-8'), self.state.encode('utf-8'), self.country.encode('utf-8'), self.prayer_times))

        self.start_countdown()
        
    def start_countdown(self):
        """Starts the countdown timer."""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None

        self.timer = Timer(1000, self.update_countdown)
        self.timer.start()

    def update_countdown(self, event=None):
        """Updates the countdown timer every second."""
        if self.next_prayer_time:
            now = datetime.datetime.now()
            remaining = self.next_prayer_time - now
            if remaining.total_seconds() > 0:
                countdown_text = str(remaining).split('.')[0]
                self.update_status_bar(countdown_text)
            else:
                if self.alertCheckbox.isSelected():
                    prayer_name = self.next_prayer.replace(" (Tomorrow)", "")
                    JOptionPane.showMessageDialog(None, 
                        "It's time for your {} prayer. \nLet's take a moment to connect with Allah.".format(prayer_name), 
                        "Prayer Reminder", 
                        JOptionPane.INFORMATION_MESSAGE)
                self.next_prayer_time = None
                self.update_prayer_times()

    def update_status_bar(self, countdown_text):
        """Updates the status bar with countdown text."""
        location = self.city or self.state or self.country
        frame = self._get_burp_frame()

        if frame:
            zdok_panel = self._get_zdok_panel(frame)
            if zdok_panel:
                existing_labels = [comp for comp in zdok_panel.getComponents() if isinstance(comp, JLabel)]
                for label in existing_labels:
                    zdok_panel.remove(label)

                all_prayer_times = ""
                # Sort prayer times and prepare all prayers times string
                for prayer in self.prayer_list:
                    if prayer in self.prayer_times:
                        if prayer == "Isha":
                            all_prayer_times += "{}: {}".format(prayer, self.prayer_times[prayer])
                        else:
                            all_prayer_times += "{}: {}\n".format(prayer, self.prayer_times[prayer])

                countdown_label = JLabel(" {} ({}): -{} [{}]".format(self.next_prayer.replace(" (Tomorrow)", ""), self.prayer_times.get(self.next_prayer.replace(" (Tomorrow)",""), 'N/A'), countdown_text, location.encode('utf-8', errors='replace') ))

                countdown_label.setToolTipText(all_prayer_times)  
                zdok_panel.setToolTipText(all_prayer_times) 

                zdok_panel.setLayout(BoxLayout(zdok_panel, BoxLayout.X_AXIS))  # Set layout for the panel
                zdok_panel.add(countdown_label)
                zdok_panel.revalidate()
                zdok_panel.repaint()

    def get_lat_lon(self):
        """Fetches latitude and longitude of the specified city, state, and country."""
        attempts = 0
        while attempts < self.max_retries:
            try:
                # Construct the URL for the API request
                url = "https://nominatim.openstreetmap.org/search?format=json&q={},{},{}".format(
                    urllib.quote(self.city.encode('utf-8')),
                    urllib.quote(self.state.encode('utf-8')),
                    urllib.quote(self.country.encode('utf-8'))
                )
                data = json.load(urllib2.urlopen(url))

                if data:
                    return data[0]['lat'], data[0]['lon']

                # Fallback: Retry with only keyword if no data found
                keyword = self.city or self.state or self.country
                fallback_url = "https://nominatim.openstreetmap.org/search?format=json&q={}".format(
                    urllib.quote(keyword.encode('utf-8'))
                )
                data = json.load(urllib2.urlopen(fallback_url))

                if data:
                    return data[0]['lat'], data[0]['lon']
                else:
                    raise Exception("Coordinates not found: {}".format(fallback_url))
            except Exception as e:
                attempts += 1
                if attempts >= self.max_retries:
                    print("Max retries reached. Error getting coordinates: {} - {}".format(url, str(e)))
                    return 0, 0
    
    def find_next_prayer(self, times, current_time):
        """Finds the next prayer time after the current time."""
        for prayer in self.prayer_list:
            if times[prayer] > current_time:
                return prayer, times[prayer]
        return 'Fajr (Tomorrow)', times['Fajr'] # If all prayers for today are passed, return Fajr for tomorrow
    

    def _get_zdok_panel(self, frame):
        """Fetches the 'Zdok' panel from the Burp Suite frame."""
        content_pane = frame.getContentPane()
        for component in content_pane.getComponents():
            if component.__class__.__name__ == "Zdok":
                return component
        return None
    
    def getTabCaption(self):
        return "Prayer Times"

    def getUiComponent(self):
        """Returns the UI component for the extension."""
        return self.panel

    def _get_burp_frame(self):
        """Fetches the Burp Suite frame to interact with the UI."""
        for frame in Frame.getFrames():
            if frame.isVisible() and frame.getTitle().startswith("Burp Suite"):
                return frame
        return None