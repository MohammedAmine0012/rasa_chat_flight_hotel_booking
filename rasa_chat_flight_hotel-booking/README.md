# Rasa Chat Flight and Hotel Booking

This project is a Rasa-based chatbot designed to assist users in booking flights and hotels. It supports various features, including flight searches, hotel reservations, and specific support for Redmi devices.

## Project Structure

- **actions/**: Contains the main actions for the Rasa chatbot.
  - **actions.py**: Main actions including flight and hotel form validations and searches.
  - **redmi_support.py**: Adds support for Redmi devices.
  - **__init__.py**: Marks the directory as a Python package.

- **config/**: Configuration settings for API integrations.
  - **api_config.py**: Contains API keys and endpoint URLs.
  - **__init__.py**: Marks the directory as a Python package.

- **data/**: Contains training data for the NLU component.
  - **nlu.yml**: Training data defining intents and examples.
  - **stories.yml**: Conversation flows for the chatbot.
  - **rules.yml**: Rules for structured conversation management.

- **domain.yml**: Defines the domain of the Rasa chatbot, including intents, entities, slots, responses, and actions.

- **models/**: Contains information about the models used in the project.
  - **README.md**: Documentation for training and evaluating models.

- **tests/**: Contains unit tests for the project.
  - **test_actions.py**: Unit tests for actions defined in actions.py.
  - **test_redmi_support.py**: Unit tests for functionality in redmi_support.py.

- **README.md**: Documentation for the project, including setup instructions and usage.

- **requirements.txt**: Lists the dependencies required for the project.

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd rasa_chat_flight_hotel-booking
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Train the Rasa model:
   ```
   rasa train
   ```

4. Run the Rasa action server:
   ```
   rasa run actions
   ```

5. Start the Rasa server:
   ```
   rasa run
   ```

## Usage

Interact with the chatbot to search for flights and hotels. The bot will guide you through the booking process, validating your inputs and providing options based on your preferences.

## Redmi Device Support

This project includes specific support for Redmi devices, ensuring compatibility and enhanced user experience for users on these devices. Refer to `actions/redmi_support.py` for more details on the implemented features.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.