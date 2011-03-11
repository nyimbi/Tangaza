#
#    Tangaza
#
#    Copyright (C) 2010 Nokia Corporation.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    Authors: Billy Odero, Jonathan Ledlie
#

import re
import logging
import string
import urllib
import urllib2

from django.http import HttpResponse
from utility import *
#from grammar import *
from appadmin import *

logger = logging.getLogger(__name__)

# XXX for testing, should be put in DB
max_group_size = 200
MAX_GROUP_SMS_SIZE = 12

##############################################################################
# Basic entry points for testing

def echo(request, phone, smsc, text):
	logger.debug ('from %s smsc %s text %s' % (phone, smsc, text))
	resp = ('Echo: from %s smsc %s text %s' % (phone, smsc, text))
	return HttpResponse(resp)

def sms_id(request, phone, smsc, id):
	logger.debug ('from %s smsc %s id %s' % (phone, smsc, id))
	resp = ('Echo: from %s smsc %s id %s' % (phone, smsc, id))
	return HttpResponse(resp)

def ping(request):
	logger.debug ('ping')
	return HttpResponse('pong')

##############################################################################
# Entry points that resolve the user, and wrap the response

@resolve_user
def update(request, user, language):
	return request_update (user,language)

#@resolve_user
def join_group (request, user, language, group_name, slot, smsc = 'mosms'):
	logger.debug("Starting join group user:%s group:%s" % (user, group_name))
	group = Vikundi.resolve (user, group_name)
	
	if group is None:
		logger.info ("smsc: %s user: %s unknown_group %s" % (smsc, user, group_name))
		return language.unknown_group(group_name)
	
	from django.conf import settings
	logger.debug('Finish him %s %s' % (user, language))#, group, slot, settings.SMS_VOICE[smsc]))
	return request_join (user, language, group, slot, settings.SMS_VOICE[smsc])

#@resolve_user
def leave_group (request, user, language, group_or_slot):
       group = Vikundi.resolve (user, group_or_slot)
       if group is None:
	       logger.info ("user %s unknown_group %s" % (user, group_or_slot))
	       return language.unknown_group(group_or_slot)
       
       return request_leave (user, language, group)

##############################################################################
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@resolve_user
def index(request, user, language):

	logger.debug ('entry point')
	
	
	# XXX set language on-the-fly
	# or pull from db based on users selection on phone
	#language = LanguageFactory.create_language('eng')
	
	if request.method == "GET":
		logger.debug ('get request')
		return request_update (user,language)
	
	raw_text = request.raw_post_data.decode('UTF8')
	
	logger.info ('user %s text %s' % (user, raw_text))
	
	# empty request
	if not raw_text:
		return request_update (user,language)
	
	msg_list = []
	tokens = raw_text.split()
	
	group_name = tokens[1] #this can be group name or slot
	
	if raw_text.startswith('@'):
		#send text message to group
		pass
	elif raw_text.startswith(language.CREATE):
		logger.debug('request create group %s' % group_name)
		#request, user, language, group_name, slot
		return request_create_group(request, user, language, group_name, '')
	elif raw_text.startswith(language.JOIN):
		logger.debug('request join group %s' % tokens[1])
		#request, user, language, group_name, slot
		return join_group(request, user, language, group_name, '')
	elif raw_text.startswith(language.INVITE):
		#(request, user, language, group_name_or_slot, invite_user_phone, smsc = 'mosms')
		logger.debug('request invite user %s to group %s' % (user, group_name))
		invited_users = ' '.join(tokens[2:])
		return invite_user_to_group(request, user, language, group_name, invited_users).encode('UTF8')
        elif raw_text.startswith(language.LEAVE):
                logger.debug('request leave group %s' % group_name)
		#leave_group (request, user, language, group_or_slot)
		return leave_group (request, user, language, group_name)
	elif raw_text.startswith(language.DELETE):
		logger.debug('request delete group %s' % group_name)
		#delete_group (request, admin, language, group_name_or_slot)
		return delete_group (request, user, language, group_name)
        elif raw_text.startswith(language.REMOVE):
		logger.debug('request remove user %s' % user)
		#delete_user_from_group (request, admin, language, group_name_or_slot, del_user_phone)
		removed_users = ' '.join(tokens[2:])
		return delete_user_from_group (request, user, language, group_name, removed_users)
	else:
		return request_update (user,language)
	

##############################################################################

@resolve_user
def index_old(request, user, language, raw_text, smsc = 'mosms'):
	from django.conf import settings
	
	logger.debug ('entry point')
	
	raw_text = urllib.unquote_plus(raw_text)
	logger.debug ("user info " + raw_text)

	sms_log = SmsLog(sender = user.phone_number, text = raw_text)
	sms_log.save()
	
	(group_token, msg_text) = string.split(raw_text, " ", 1)
	(blank, group_name_or_slot) = string.split(group_token, "@")
	
	logger.info ("user %s text %s" % (user, msg_text))
	
	# group_name is None resolves to user's default group
	group = Groups.resolve (user, group_name_or_slot)
	
	if group is None:
		logger.debug ("group name %s is null" % group_name_or_slot)
		# user provided a group name, but it doesn't exist
		return language.unknown_group(group_name_or_slot)
	elif group.get_user_count() > MAX_GROUP_SMS_SIZE:
		return language.group_too_big_for_sms(settings.SMS_VOICE[smsc])
	else:
		logger.debug ("group name %s resolved %s" % (group_name_or_slot, group))
		
		if group_name_or_slot is None or len(group_name_or_slot) < 1:
			# a "tweet" to default group
			# "foo"     -> send msg "foo #phone" to #group
			msg_text = "%s @%s" % (msg_text[:140], group.group_name)
		else:
			# "#group"     -> send msg "#group" to #group
			# "#group foo" -> send msg "#group foo" to #group
			import re
			identity = re.sub('^2547', '07', user.phone_number)
			
			if user.name_text != None : identity = user.name_text
			msg_text = "%s %s@%s" % (msg_text[:140], identity, group.group_name)
			
		
	return request_send (user, language, msg_text, group, settings.SMS_VOICE[smsc])


##############################################################################
def request_join (user, language, group, slot, origin):
	
	# SMS-only if no slot given
	
	logger.debug ("join group %s slot %s user %s" % (group, slot, user))
	
	# XXX group_name??
	#if group is None:
	#	return language.unknown_group(group_name)
	
	if user.is_member(group):
		return language.already_member(group)
	
	if not user.has_empty_slot(): #and slot >= 0:
		return language.user_has_no_empty_slots ()
	
	if len(slot) < 1: #meaning user never provided a slot number
		slot = auto_alloc_slot(user)
	
	if slot == 0 or (slot > 0 and not user.slot_is_empty(slot)):
		return language.slot_not_free(slot)
	
	if not group.is_public() and not user.was_invited(group):
		return language.cannot_join_without_invite (group)
	
	if group.get_user_count() >= max_group_size:
		return 'Sorry, groups sizes are limited, so you cannot be added to %s' % group.group_name
	
	
	user.join_group(group, slot, origin)
	
	return language.joined_group(group, slot)

##############################################################################

def request_send(user, language, msg_text, group, origin):

	if not user.is_member(group):
		logger.info ("nonmember user %s tried to send to group %s" % (user, group))
		return language.nonmember_cannot_send(group)
	
	if not user.can_send(group):
		logger.info ("member user %s tried to send to group %s" % (user, group))
		return language.member_cannot_send(group)
	
	logger.info ("member user %s sent OK to group %s text %s" % (user, group, msg_text))
	
	# check for errors
	receipt_count = group.send_msg (user, msg_text, origin)
	
	# XXX turn into language
	if receipt_count == 0:
		return ('Sorry, no one to send to.  Invite friends with invite %s' % group.group_name)
	else:
		#if receipt_count == 1:
		#return ('T: %s <1>' % msg_text)
		#else:
		return ('T<%d>: %s' % (receipt_count, msg_text))


##############################################################################

def request_update (user, language):

	import string
	# XXX Still have to modify this to be lang indep
	
	update = ""
	#1: current groups
	groups = UserGroups.objects.filter(user = user).extra(order_by = ['slot'])
	
	g = [str(x.slot) + "@" + x.group.group_name for x in groups]
	g = string.join(g).replace(user.phone_number, 'mine') + ".\n"
	update += g
	
	#2: invitations
	invitations = Invitations.objects.filter(completed='no', invitation_to = user)
	i = ""
	if len(invitations) > 0:
		i = ["from: " + x.invitation_from.userphones_set.get().phone_number + "->"
		     + x.group.group_name + "; " for x in invitations]
	i = "Invitations(" + str(len(invitations)) + ") " + string.join(i) + ".\n"
	update += i
	
	#3: new messages
	msgs = SubMessages.objects.filter(dst_user = user, heard = 'no')

	update += "Messages(" + str(len(msgs)) + ")"
	
	logger.debug ("user %s" % user)	
	return language.user_update(update)

##############################################################################
def request_leave (user, language, group):
	
	if group is None:
		logger.info ("user %s unknown_group %s" % (user, group))
		return language.unknown_group(name_or_slot)
	
	if not user.is_member(group):
		logger.info ("user %s not in group %s" % (user, group))
		return language.user_not_in_group(user, group)
	
	if user.is_admin(group):
		logger.debug ("admin=yes")
		
		if user.is_mine (group):
			# cannot delete our default group
			logger.debug ("mine=yes")
			logger.info ("user %s cannot leave own group" % user)
			return language.cannot_leave_own_group()
		
		logger.debug ("mine=no")
		
		if group.get_admin_count () == 1:
			logger.debug ("admin_count = 1")
			
			if group.get_user_count () > 1:
				logger.info ("user %s cannot leave only admin group %s" % (user, group))
				return language.cannot_leave_when_only_admin(group)
			else:
				# just one user: us
				# keep this in for now and test deletions
				user.leave_group(group)
				#Groups.delete (user, group)
				group.delete()
				logger.info ("user %s leaving and deleting group %s" % (user, group))
				return ' '.join([language.user_left_group , language.group_deleted (group)])
		else:
			
			logger.debug ("admin_count > 1")
			logger.info ("admin user %s leaving group %s" % (user, group))
			user.leave_group(group)			
			
	else:
		
		# if we're not an admin, there must be other member
		# of the group, so we are free to leave
		logger.debug ("normal leave")
		logger.info ("normal user %s leaving group %s" % (user, group))
		user.leave_group(group)
	
	return language.user_left_group(group.group_name)
