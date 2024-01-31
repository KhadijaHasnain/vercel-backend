class LessonPlannerPrompt:
    def __init__(self, teacher_type):
        self.teacher_type = teacher_type

    def get_prompt(self):
        if self.teacher_type == "elementary school teacher":
            return "You will take on a role of elementary school teacher "
        
        if self.teacher_type == "middle school teacher":
            return "You will take on a role of middle school teacher "
        
        if self.teacher_type == "high school professor":
            return "You will take on a role of high school professor "
        
        if self.teacher_type == "university professor":
            return "You will take on a role of university professor "
        
        

# lesson_planner_prompt = LessonPlannerPrompt("elementary school teacher")
# print(lesson_planner_prompt.get_prompt())