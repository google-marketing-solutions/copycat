# Copycat Demo UI

This subpackage of Copycat contains the code that runs the Copycat Demo UI. 
This is a user interface that can be deployed from Google Colab or on Google 
Cloud Run. It is built using [Mesop](https://google.github.io/mesop/), which is 
a python package designed to:

>Create web apps without the complexity of frontend development. Used at 
Google for rapid AI app development.
> 
> *-- Mesop Documentation*

This UI is designed for demos and prototyping, but not for large scale 
deployments. For that, users are expected to either use the Copycat-on-Sheets
solution which builds on top of Google Sheets, or build their own custom 
implementation using the Copycat python module.

## Unit Testing

As Mesop is designed for prototyping, we do not unit test the front end code. 
Instead we keep as much of the logic in the main copycat repo (which is tested),
and only the front-end parts are left in the UI which are untested. 
