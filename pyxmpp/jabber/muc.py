#
# (C) Copyright 2003 Jacek Konieczny <jajcus@bnet.pl>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License Version
# 2.1 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import libxml2

from pyxmpp.utils import to_utf8,from_utf8
from pyxmpp.stanza import common_doc,common_root
from pyxmpp.presence import Presence
from pyxmpp.message import Message
from pyxmpp.iq import Iq

MUC_NS="http://jabber.org/protocol/muc"
MUC_USER_NS=MUC_NS+"#user"
MUC_ADMIN_NS=MUC_NS+"#admin"
MUC_OWNER_NS=MUC_NS+"#owner"

class MucXBase:
	def __init__(self,node_or_ns,copy=1,parent=None):
		if type(node_or_ns) is StringType:
			node_or_ns=unicode(node_or_ns,"utf-8")
		self.node=None
		self.borrowed=0
		if isinstance(node_or_ns,libxml2.xmlNode):
			if copy:
				self.node=node_or_ns.docCopyNode(common_doc,1)
				common_root.addChild(self.node)
			else:
				self.node=node_or_ns
				self.borrowed=1
			if copy:
				ns=node_or_ns.ns()
				xmlextra.replace_ns(self.node,ns,None)
				xmlextra.remove_ns(self.node,ns)
		elif isinstance(node_or_ns,MucXBase):
			if not copy:
				raise ErrorNodeError,"MucXBase may only be copied"
			self.node=node_or_ns.node.docCopyNode(common_doc,1)
			common_root.addChild(self.node)
		elif node_or_ns is None:
			raise ErrorNodeError,"Muc X node namespace not given"
		else:
			if parent:
				self.node=parent.newChild(None,"x",None)
				self.borrowed=1
			else:
				self.node=common_root.newChild(None,"x",None)
			ns=self.node.newNs(ns,None)
			self.node.setNs(ns)
		
	def __del__(self):
		if self.node:
			self.free()

	def free(self):
		if not self.borrowed:
			self.node.unlinkNode()
			self.node.freeNode()
		self.node=None

	def free_borrowed(self):
		self.node=None

	def xpath_eval(self,expr):
		ctxt = common_doc.xpathNewContext()
		ctxt.setContextNode(self.node)
		ctxt.xpathRegisterNs("muc",self.node.ns().getContent())
		ret=ctxt.xpathEval(expr)
		ctxt.xpathFreeContext()
		return ret

	def serialize(self):
		return self.node.serialize()

class MucX(MucXBase):
	ns=MUC_NS
	def __init__(self,node_or_ns,copy=1,parent=None):
		MucXBase.__init__(self,node_or_ns,copy=copy,parent=parent)
	# FIXME: set/get password/history

class MucItem:
	def __init__(self,node_or_affiliation,jid=None,nick=None,role=None,actor=None,reason=None):
		if isinstance(node_or_affiliation,libxml2.xmlNode):
			self.__from_node(node_or_affiliation)
		else:
			self.__init(node_or_affiliation,jid,nick,role,actor,reason)

	def __init(self,affiliation,jid=None,nick=None,role=None,actor=None,reason=None):
		if affiliation not in affiliations:
			raise ValueError,"Bad affiliation"
		self.affiliation=affiliation
		if role not in roles:
			raise ValueError,"Bad role"
		self.role=role
		if jid:
			self.jid=JID(jid)
		else:
			self.jid=None
		if actor:
			self.actor=JID(actor)
		else:
			self.actor=None
		self.nick=nick
		self.reason=reason

	def __from_node(self,node):
		actor=None
		reason=None
		for n in node.children:
			ns=n.ns()
			if ns and ns.getContent()!=MUC_USER_NS:
				continue
			if n.name=="actor":
				actor=n.getContent()
			if n.name=="reason":
				reason=n.getContent()
		self.__init(
			from_utf8(node.prop("affiliation")),
			from_utf8(node.prop("jid")),
			from_utf8(node.prop("nick")),
			from_utf8(node.prop("role")),
			from_utf8(actor),
			from_utf8(reason),
			);

	def make_node(self,parent):
		n=parent.newChild(parent.ns(),"item",None)
		if self.actor:
			n.newTextChild(parent.ns(),"actor",to_utf8(self.actor))
		if self.reason:
			n.newTextChild(parent.ns(),"reason",to_utf8(self.reason))
		n.setProp("affiliation",to_utf8(self.affiliation))
		n.setProp("role",to_utf8(self.role))
		if self.jid:
			n.setProp("jid",to_utf8(self.jid.as_unicode()))
		if self.nick:
			n.setProp("nick",to_utf8(self.nick.as_unicode()))
		return n

class MucXUser(MucXBase):
	ns=MUC_NS_USER
	def __init__(self,node_or_ns,copy=1,parent=None):
		MucXBase.__init__(self,node_or_ns,copy=copy,parent=parent)
	def get_items(self):
		ret=[]
		for n in self.children:
			n=n.ns()
			if ns and ns.getContent()!=MUC_USER_NS:
				continue
			if n.name=="item":
				ret.append(MucItem(n))
			# FIXME: alt,decline,invite,password,status
		return ret
	def clear(self):
		for n in list(self.children):
			n=n.ns()
			if ns and ns.getContent()!=MUC_USER_NS:
				continue
			n.unlinkNode()
			n.freeNode()
	def add_item(self,item):
		if item.__class__ not in (MucItem,):
			raise TypeError,"Bad item type for muc#user"
		item.make_node(self)

class MucStanzaExt:
	def __init__(self):
		if not has_attr("node"):
			raise RuntimeError,"Abstract class called"
		self.muc_x=None

	def get_muc_x(self):
		x=None
		for n in self.node.children:
			if n.name!="x":
				continue
			ns=n.ns()
			if not ns:
				continue
			ns_uri=ns.getContent()
			if ns_uri==MUC_NS:
				return MucX(n)
			if ns_uri==MUC_USER_NS:
				return MucUserX(n)
			if ns_uri==MUC_ADMIN_NS:
				return MucAdminX(n)
			if ns_uri==MUC_OWNER_NS:
				return MucOwnerX(n)

	def clear_muc_x(self):
		if self.muc_x:
			self.muc_x.free_borrowed()
			self.muc_x=None
		x=None
		for n in list(self.node.children):
			if n.name!="x":
				continue
			ns=n.ns()
			if not ns:
				continue
			ns_uri=ns.getContent()
			if ns_uri in (MUC_NS,MUC_USER_NS,MUC_ADMIN_NS,MUC_OWNER_NS):
				n.unlinkNode()
				n.freeNode()
				
	def muc_free(self):
		if self.muc_x:
			self.muc_x.free_borrowed()

class MucPresence(Presence,MucStanzaExt):
	def __init__(self,node=None,**kw):
		self.node=None
		MucStanzaExt.__init__(self)
		apply(Presence.__init__,[self,node],kw)

	def copy(self):
		return MUCPresence(self)

	def make_join_request(self):
		self.clear_muc_x()
		self.muc_x=MucX(MUC_NS,parent=self.node)

	def free(self):
		self.muc_free()
		Presence.free(self)
