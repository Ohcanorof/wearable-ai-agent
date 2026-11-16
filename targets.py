#targets.py
# This file will define the werable device that we want to
# specifically research

#categories allowed:
ALLOWED_CATEGORIES = {
    "Smartwatch",
    "Fitness Tracker",
    "Smart Ring",
    "Fitness Band",
    "Sports Watch",
}

#the collumns that we want based on the main data set we are using (P.P)

CSV_COLUMNS = [
    "Test_Date",
    "Device_Name",
    "Brand",
    "Model",
    "Category",
    "Price_USD",
    "Battery_Life_Hours",
    "Heart_Rate_Accuracy_Percent",
    "Step_Count_Accuracy_Percent",
    "Sleep_Tracking_Accuracy_Percent",
    "Water_Resistance_Rating",
    "User_Satisfaction_Rating",
    "GPS_Accuracy_Meters",
    "Connectivity_Features",
    "Health_Sensors_Count",
    "App_Ecosystem_Support",
    "Performance_Score",
]

#This is the controlled list of the brands and models we want to look at specifically
#this is a python list of dictionaries w/ target brand and devices
TARGET_DEVICES = [
    {
        "brand": "Apple",
        "model": "Watch Series 10",
        "category": "Smartwatch",
    },
    {
        "brand": "Apple",
        "model": "Watch Ultra 2",
        "category": "Smartwatch",
    },
    {
        "brand": "Garmin",
        "model": "Forerunner 265",
        "category": "Sports Watch",
    },
    {
        "brand": "Garmin",
        "model": "Venu 3",
        "category": "Smartwatch",
    },
    {
        "brand": "Oura",
        "model": "Ring Gen3",
        "category": "Smart Ring",
    },
    {
        "brand": "Oura",
        "model": "Ring 4",
        "category": "Smart Ring",
    },
    {
        "brand": "WHOOP",
        "model": "4.0",
        "category": "Fitness Band",
    },
    {
        "brand": "WHOOP",
        "model": "5.0",
        "category": "Fitness Band",
    },
    {
        "brand": "Samsung",
        "model": "Galaxy Watch7",
        "category": "Smartwatch",
    },
    {
        "brand": "Samsung",
        "model": "Galaxy Watch Ultra",
        "category": "Smartwatch",
    },
    {
        "brand": "Fitbit",
        "model": "Charge 6",
        "category": "Fitness Tracker",
    },
    {
        "brand": "Fitbit",
        "model": "Sense 2",
        "category": "Smartwatch",
    },
]

#validate_targets() is supposed to catch config mistakes before going ahead and spending credits (money)
#catches duplicates too (defensive programming)
def validate_targets():
    """Check that the target list is correctly configured."""

    seen_devices = set()

    for device in TARGET_DEVICES:
        brand = device["brand"]
        model = device["model"]
        category = device["category"]

        #each device needs to have a name and model, else dont use it
        if not brand or not model:
            raise ValueError("A device is missing its brand or model!!!!")

        #the category needs to match the list w/ allowed categores
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"invalid category: {category}")

        #dont process the same model twice, need to be efficient, so we need to 
        #convert the names and models to lower case
        device_name = (brand.lower(), model.lower())

        if device_name in seen_devices:
            raise ValueError(f"Duplicate device: {brand} {model}")

        seen_devices.add(device_name)

    return True

#get_targets is the inteface for this part of the agent, the main.py file will use this eventyally
#to return thel ist of targets
def get_targets():
    """Return the validated target list."""

    validate_targets()
    return TARGET_DEVICES

if __name__ == "__main__": #tells python to run the test section only when executing targets.py directly
    devices = get_targets()
    print(f"Total target devices: {len(devices)}")
    print(f"CSV columns: {len(CSV_COLUMNS)}")
    print()

    for device in devices:
        print(f"{device['brand']} {device['model']}")


        




