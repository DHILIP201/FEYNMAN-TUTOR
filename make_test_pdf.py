"""Helper script to create a valid, extractable PDF for E2E tests."""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def make_pdf():
    doc = SimpleDocTemplate("test_study_material.pdf", pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor='#4F46E5',
        spaceAfter=20
    )
    story.append(Paragraph("Study Guide: Recursion Depth and Stack Bounds", title_style))
    story.append(Spacer(1, 12))
    
    # Body Styles
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['BodyText'],
        fontSize=12,
        leading=16,
        spaceAfter=10
    )
    
    # Document content
    p1 = ("Recursion is a programming technique where a function calls itself "
          "directly or indirectly to solve a problem. Every recursive function "
          "requires two fundamental components: a base case that halts the execution, "
          "and a recursive step that progresses towards the base case. Without a proper "
          "base case, a recursive function will loop indefinitely, consuming stack memory.")
    story.append(Paragraph(p1, body_style))
    
    p2 = ("The call stack is a stack data structure that stores information about the active "
          "subroutines of a computer program. Each recursive call creates a new stack frame "
          "containing local variables, arguments, and return addresses. The depth of recursion "
          "refers to the number of stack frames currently active. If the depth exceeds the stack "
          "bounds, a Stack Overflow exception is raised by the operating system.")
    story.append(Paragraph(p2, body_style))
    
    p3 = ("To prevent stack overflows, developers can trace execution trees, limit "
          "the recursion depth using guards, or convert the algorithm into an iterative version "
          "using a loop and an explicit stack array. In python, the sys.getrecursionlimit() "
          "function returns the current stack depth configuration, which defaults to 1000.")
    story.append(Paragraph(p3, body_style))
    
    doc.build(story)
    print("SUCCESS: test_study_material.pdf successfully created with extractable text.")

if __name__ == '__main__':
    make_pdf()
