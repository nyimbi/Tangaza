#!/usr/bin/perl
#
#    Tangaza
#
#    Copyright (C) 2010-2012 Nokia Corporation.
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


use strict;
use warnings;
use Nokia::Common::GatewayHttpSMSRelay;

my $self;
my $sender = "18576548538";
my $msg = "hello world";

my $content = &Nokia::Common::GatewayHttpSMSRelay::post_msg($self,$sender,$msg);

print "content $content\n";

