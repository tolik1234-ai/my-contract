from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

def profile(request):
    return render(request, 'profile.html')

def updates(request):
    return render(request, 'updates.html')

def my_contacts(request):
    return render(request, 'my_contacts.html')

def docs(request):
    return render(request, 'docs.html')