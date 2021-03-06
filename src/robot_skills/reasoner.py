#! /usr/bin/env python
import roslib; roslib.load_manifest('robot_skills')
import rospy
import threading
from psi import *
import std_srvs.srv
from obj_in_gripper.srv import ObjectInGripper, ObjectInGripperRequest

#TODO Loy: Convert most of __main__ to doctests.

def term_to_point(term):
    if term.functor == "point":
        if term[0].is_number() and term[0].is_number() and term[0].is_number():
            return (term[0].get_number(), term[1].get_number(), term[2].get_number())
    return ()

class Reasoner(object):
    """Interface to Amigo's reasoner. 
    Converts __getattr__-calls into terms"""
    def __init__(self, wait_service=False):
        self._lock = threading.RLock()      
        if wait_service:
            rospy.loginfo("waiting for reasoner service in reasoner.__init__")
            # Sjoerd: Client _init_ already waits for service  
            #rospy.wait_for_service('reasoner/query',timeout=2)#rospy.Duration(2.0))
            rospy.loginfo("service connected.")
            
            # Object in gripper service
            rospy.loginfo("Waiting for obj_in_gripper service")
            rospy.wait_for_service("/obj_in_gripper", timeout=2.0)

        self.client = Client("/reasoner")
            
        #self.query              = rospy.ServiceProxy('/reasoner/query', tue_reasoner_msgs.srv.Query)
        #self.assert_knowledge   = rospy.ServiceProxy('/reasoner/assert', tue_reasoner_msgs.srv.Assert)
        self.sv_reset            = rospy.ServiceProxy('/wire/reset', std_srvs.srv.Empty)

        #self.q = self.QueryConstructor()
        
        self.sv_object_in_gripper = rospy.ServiceProxy("/obj_in_gripper", ObjectInGripper)
        
        self.attached_IDs = {}

    def close(self):
        pass

    def query(self, term):
        return self.client.query(term)

    def assertz(self, *facts):
        for fact in facts:
            self.client.query(Compound("assert", fact))

        # reasoning_assert = tue_reasoner_msgs.srv.AssertRequest()
        # for fact in facts:
        #     reasoning_assert.facts += [term_to_msg(fact)]
        # reasoning_assert.action = tue_reasoner_msgs.srv.AssertRequest.ASSERTZ
        
        # #print reasoning_assert
        # #import ipdb; ipdb.set_trace()
        # result = self.assert_knowledge(reasoning_assert)
        # if result.error == '':
        #     return True
        # else:
        #     #Abusing the AssertionError here, it is meant for use with th 'assert' python keyword.
        #     raise AssertionError("Facts {0} could not be be asserted: '{1}'".format(facts, result))

    def exists_predicate(self, predicatename):
        raise NotImplementedError()

    def __getattr__(self, name):
        """The __getattr__-magic method of objects overrides the . operator, like the . in someobject.do_something.
        For someobject, Python internally calls the __getattr__(self, name)-method on someobject, 
        passing do_something to the variable name, and someobject to self.
        Overriding this method allows you to define attributes for an object that it does not really have!
        This feature is used here for Reasoner. 
        A Reasoner-object may not have a method defined for the predicate-name you want to use,
        but it *generates* a function or object based on the predicate-name you passed. 
        This function or object is then returned by __getattr__, and that way, 
        the generated function *acts* like it is a real method or attribute of Reasoner."""
        replacers = {"_class":"class", "_not":"not"}
        if replacers.has_key(name):
            name = replacers[name]

        def term(*args, **kwargs):
            compound = Compound(name, *args)
            compound.reasoner = self #TODO: make this a keyword argument?
            return compound
        return term
        
    def attach_object_to_gripper(self, ID, frame_id, grasp):
        rospy.loginfo("Attach object {0} to frame {1} = {2}".format(ID, frame_id, grasp))

        ID = str(ID)	

        request = ObjectInGripperRequest()
        request.ID = ID
        request.frame = frame_id
        request.grasp = grasp
        
        self.attached_IDs[ID] = frame_id
        try:
            result = self.sv_object_in_gripper(request)
        except rospy.ServiceException, se:
            rospy.logerr("ObjectInGripperRequest failed, ignoring and continuing without")
            return False
        return result
    
    def detach_all_from_gripper(self, frame_id):
        rospy.loginfo("Detaching all objects from gripper. Attached IDs are: {0}".format(self.attached_IDs))
        
        #import ipdb; ipdb.set_trace()
        #try:
        #    IDs_at_frame = [ID for ID,frame in self.attached_IDs.iteritems() if frame == frame_id]
        #    for ID in IDs_at_frame:
        #        request = ObjectInGripperRequest()
        #        request.ID = ID
        #        request.frame = frame_id
        #        request.grasp = False
        #    
        #        result = self.sv_object_in_gripper(request)
        #except:
        #    rospy.loginfo("Passing")
        request = ObjectInGripperRequest()
        request.frame = frame_id
        request.grasp = False
        result = self.sv_object_in_gripper(request)

    def set_time_marker(self, name):
        self.query(Compound("retractall", Compound("time_marker", name, "X")))
        self.query(Compound("assert", Compound("time_marker", name, Constant(rospy.Time.now().secs))))

    # returns rospy.Duration
    def get_time_since(self, name):
        res = self.query(Compound("time_marker", name, "Time"))
        if not res:
            rospy.logerr("No time marker found with name '" + str(name) + "'")
            return None
        
        t_secs = float(res[0]["Time"])
        return rospy.Time.now() - rospy.Time(t_secs)

    def reset(self):
        self.detach_all_from_gripper("/amigo/grippoint_left")
        self.detach_all_from_gripper("/amigo/grippoint_right")
        self.sv_reset()

if __name__ == "__main__":
    rospy.init_node("amigo_reasoner_executioner", log_level=rospy.DEBUG)
    reasoner = Reasoner()  

    #q = reasoner.QueryConstructor()

    term1 = Compound("class", "X", "coke")
    term2 = Compound("class", "obj1", "Class")
    term3 = Compound("object_at_coordinates", "obj1", Compound("pose", "X", "Y", "Phi"))
    term4 = Compound("object_at_coordinates", "obj2", Compound("pose", "X", "Y", "Phi"))
    term5 = Conjunction(Compound("class", "Object", "coke"), Compound("object_at_coordinates", "Object", Compound("pose", "X", "Y", "Phi")))
    
    term6 = Compound("visited", "obj1")
    term7 = Conjunction(Compound("class", "Object", "coke"), 
                        Compound("object_at_coordinates", "Object", 
                            Compound("pose", "X", "Y", "Phi")
                                ),
                        Compound('not', Compound('visited', 'Object')))

    term8 = Compound("class", "Object", "coke") & \
            Compound("object_at_coordinates", "Object", 
                            Compound("pose", "X", "Y", "Phi")) & \
            Compound('not', Compound('visited', 'Object'))

    term9 = reasoner._class("Object", "coke") & \
            reasoner.object_at_coordinates("Object", 
                            reasoner.pose("X", "Y", "Phi")) & \
            reasoner._not(reasoner.visited('Object'))    

    term10 = (reasoner._class("Object", "coke") | reasoner._class("Object", "sandwich")) & \
            reasoner.object_at_coordinates("Object", 
                            reasoner.pose("X", "Y", "Phi")) & \
            reasoner._not(reasoner.visited('Object'))

    term11 = reasoner.unreachable("couch_table_A")

    term12 = reasoner._class("obj1", "Class")
    #answer13 = reasoner._class("obj1", "Class")() #NOTE the () at the end!

    answer1     = reasoner.query(term1)
    answer2     = reasoner.query(term2)
    answer3     = reasoner.query(term3)
    answer4     = reasoner.query(term4)
    answer5     = reasoner.query(term5)
    assert6     = reasoner.assertz(term6)
    answer7     = reasoner.query(term7)
    answer8     = reasoner.query(term8)
    answer9     = reasoner.query(term9)
    answer10    = reasoner.query(term10)
    assert11    = reasoner.assertz(term11)
    #answer12    = term12()
    #answer12a   = term12(summarize=False)

    print answer1
    print answer2
    print answer3
    print answer4
    print assert6
    print answer7
    print answer8
    print answer9
    print answer10
    print assert11
    #print answer12
    #print answer12a 
    #print answer13

    assert answer8 == answer7
    assert answer9 == answer7
    #assert answer2 == answer12
    #assert answer2 == answer12a
    #assert answer2 == answer13

    tracker = reasoner.position("Object", reasoner.point("X", "Y", "Z"))
    print reasoner.query(tracker)
