from datetime import date, time
from typing import *

type AppointmentModel = AppointmentModel

class AppointmentModel:
    def __init__(self):
        self.appointmentDate : date = None
        self.appointmentTime : time = None
        self.clientName = None
        self.petName = None
        self.reason = None
        self.notes = None
        self.doctor = None
        self.type = None
        self.cssPath = None
        
        self.weight : float = None
        self.heartRate : int = None
        self.bodyConditionScore : int = None
        
        
        self.masterProblems = []
        
        # Clinical Exam Page
        self.historyText = None
        self.physicalExamText = None
        self.assessmentText = None
        self.planText = None
        
        # Diagnostic And Treatment Page
        self.medications = []
        self.diagnosticResults = []
        
        # Vaccinations Page
        self.vaccinations = []
        
        # In Clinic Notes Page
        self.clinicNotes = None
        
        self.Attachments = []

    def HasBasicInfo(self):
        return (
            self.appointmentDate is not None and 
            self.appointmentTime is not None and 
            self.clientName is not None and 
            self.petName is not None and
            self.doctor is not None and
            self.type is not None and
            self.cssPath is not None
        )
        
    def IsFullyFilled(self):
        return (
            self.HasBasicInfo()
        )
        
    def __eq__(self, other) -> bool:
        if "AppointmentModel" not in type(other):
            return False
        return (
            self.appointmentDate == other.appointmentDate and
            self.appointmentTime == other.appointmentTime and
            self.clientName == other.clientName and
            self.petName == other.petName
        )
                